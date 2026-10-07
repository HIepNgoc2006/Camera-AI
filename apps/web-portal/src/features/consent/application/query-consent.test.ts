import { describe, expect, it, vi } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type PermissionCode,
  type SessionSnapshot,
} from "@/features/auth/domain/route-access";
import type { ConsentQuery } from "@/features/consent/domain/consent-view";
import type { ConsentRecordView } from "@/features/consent/domain/consent-view";
import type {
  ConsentReadProvider,
  ConsentReadProviderResult,
  ConsentPage,
} from "./query-consent";
import { queryConsentListView } from "./query-consent";

const NOW = new Date("2026-10-07T12:00:00.000Z");
const CONSENT_ID = "00000000-0000-4000-8000-00000000007c";

function fakeSession(
  permissions: readonly PermissionCode[],
  overrides: Partial<SessionSnapshot> = {},
): SessionSnapshot {
  return {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "authenticated",
    actorId: "actor_test_001",
    tenantId: "tenant_test_001",
    schoolId: "school_test_001",
    mfaState: "verified",
    issuedAt: "2026-10-07T00:00:00.000Z",
    warningStartsAt: "2026-10-07T11:30:00.000Z",
    inactivityExpiresAt: "2026-10-07T18:00:00.000Z",
    absoluteExpiresAt: "2026-10-08T00:00:00.000Z",
    authorization: {
      policyVersion: AUTHORIZATION_POLICY_VERSION,
      permissions,
    },
    ...overrides,
  };
}

function syntheticRecord(
  overrides: Partial<ConsentRecordView> = {},
): ConsentRecordView {
  return {
    consentId: CONSENT_ID,
    subjectActorRef: "student_test_002",
    displayLabel: "Đồng ý điểm danh — thử nghiệm",
    purposeCode: "attendance",
    policyVersion: "consent_gate_v1",
    status: "granted",
    scopeSchoolId: "school_test_001",
    validFrom: "2026-09-01T00:00:00.000Z",
    validUntil: null,
    withdrawalState: null,
    version: 2,
    ...overrides,
  };
}

function syntheticPage(): ConsentPage {
  return { items: [syntheticRecord()], nextCursor: null };
}

function providerReturning(
  result: ConsentReadProviderResult,
): ConsentReadProvider {
  return { readList: vi.fn().mockResolvedValue(result) };
}

const VIEW_ONLY: readonly PermissionCode[] = ["consent.view_metadata"];
const VIEW_AND_CORRECT: readonly PermissionCode[] = [
  "consent.view_metadata",
  "consent.correct",
];

describe("session gate", () => {
  it.each([null, undefined, {}, { status: "unknown" }, "session"])(
    "denies without a valid session (%j)",
    async (session) => {
      const provider = providerReturning({
        kind: "success",
        page: syntheticPage(),
      });
      expect(
        await queryConsentListView({
          session,
          rawQuery: {},
          provider,
          capabilities: { readActive: true, mutationActive: true },
          now: NOW,
        }),
      ).toEqual({ kind: "denied" });
      expect(provider.readList).not.toHaveBeenCalled();
    },
  );

  it("denies an expired session before any provider call", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider,
        capabilities: { readActive: true, mutationActive: true },
        now: new Date("2026-10-09T00:00:00.000Z"),
      }),
    ).toEqual({ kind: "denied" });
    expect(provider.readList).not.toHaveBeenCalled();
  });

  it("denies an admin-only permission set before any provider call", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryConsentListView({
        session: fakeSession(["role_assignment.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "denied" });
    expect(provider.readList).not.toHaveBeenCalled();
  });
});

describe("query validation", () => {
  it("reports deterministic validation failure for forged scope keys", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { guardianSubjectRef: "guardian_evil" },
        provider,
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "validation", errorCode: "CONSENT_FILTER_INVALID" });
    expect(provider.readList).not.toHaveBeenCalled();
  });

  it("reports validation failure for a malformed limit", async () => {
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { limit: "1000" },
        provider: providerReturning({ kind: "success", page: syntheticPage() }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "validation", errorCode: "CONSENT_FILTER_INVALID" });
  });
});

describe("runtime capabilities", () => {
  it("returns unavailable without any provider call when read is inactive", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider,
        capabilities: { readActive: false, mutationActive: false },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
      canRecordDecision: false,
    });
    expect(provider.readList).not.toHaveBeenCalled();
  });
});

describe("authorized provider reads", () => {
  it("narrows the authoritative scope from the server session only", async () => {
    const readList = vi
      .fn()
      .mockResolvedValue({ kind: "success", page: syntheticPage() });
    await queryConsentListView({
      session: fakeSession(VIEW_AND_CORRECT),
      rawQuery: { limit: "50" },
      provider: { readList },
      capabilities: { readActive: true, mutationActive: true },
      now: NOW,
    });

    expect(readList).toHaveBeenCalledWith({
      query: { cursor: null, limit: 50 } satisfies ConsentQuery,
      scope: {
        tenantId: "tenant_test_001",
        schoolId: "school_test_001",
        actorId: "actor_test_001",
      },
    });
  });

  it("maps provider denial to the public denied state", async () => {
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({ kind: "denied_or_not_found" }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "denied" });
  });

  it("maps an upstream exception to sanitized unavailable", async () => {
    const readList = vi.fn().mockRejectedValue(new Error("internal detail"));
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: { readList },
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
      canRecordDecision: false,
    });
  });

  it("returns empty for a page with no rows", async () => {
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: { items: [], nextCursor: null },
        }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "empty",
      query: { cursor: null, limit: 25 },
      canRecordDecision: false,
    });
  });

  it("returns the decoded page for an authorized actor", async () => {
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_AND_CORRECT),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: syntheticPage(),
        }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "success",
      query: { cursor: null, limit: 25 },
      page: syntheticPage(),
      canRecordDecision: true,
    });
  });

  it("keeps record-decision hidden without the correct permission", async () => {
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: syntheticPage(),
        }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toMatchObject({ canRecordDecision: false });
  });

  it("keeps record-decision hidden when the mutation runtime is inactive", async () => {
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_AND_CORRECT),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: syntheticPage(),
        }),
        capabilities: { readActive: true, mutationActive: false },
        now: NOW,
      }),
    ).toMatchObject({ canRecordDecision: false });
  });
});

describe("provider payload safety", () => {
  type UnsafeOverride = Partial<Omit<ConsentRecordView, "status">> & {
    status?: string;
  };
  it.each([
    {
      case: "cross-school scope leak",
      override: { scopeSchoolId: "school_other_002" },
    },
    {
      case: "identity proof material",
      override: {},
      extra: { identity_document: "canary" },
    },
    {
      case: "duplicate consent id",
      override: {},
      duplicate: true,
    },
    {
      case: "unapproved purpose",
      override: { purposeCode: "marketing" },
    },
    {
      case: "unknown consent status",
      override: { status: "superuser" } satisfies UnsafeOverride,
    },
    {
      case: "unknown withdrawal state",
      override: { withdrawalState: "deleted" },
    },
    {
      case: "invalid version",
      override: { version: 0 },
    },
    {
      case: "non-canonical instant",
      override: { validFrom: "2026-09-01" },
    },
  ] as ReadonlyArray<{
    case: string;
    override: UnsafeOverride;
    extra?: Record<string, unknown>;
    duplicate?: boolean;
  }>)(
    "rejects unsafe payload: $case",
    async ({ override, extra, duplicate }) => {
      const row: ConsentRecordView = {
        consentId: CONSENT_ID,
        subjectActorRef: "student_test_002",
        displayLabel: "Đồng ý điểm danh — thử nghiệm",
        purposeCode: "attendance",
        policyVersion: "consent_gate_v1",
        status: "granted",
        scopeSchoolId: "school_test_001",
        validFrom: "2026-09-01T00:00:00.000Z",
        validUntil: null,
        withdrawalState: null,
        version: 2,
        ...override,
        ...(extra ?? {}),
      } as ConsentRecordView;
      const items = duplicate ? [row, row] : [row];
      const result: ConsentReadProviderResult = {
        kind: "success",
        page: { items, nextCursor: null },
      };

      expect(
        await queryConsentListView({
          session: fakeSession(VIEW_ONLY),
          rawQuery: {},
          provider: providerReturning(result),
          capabilities: { readActive: true, mutationActive: true },
          now: NOW,
        }),
      ).toEqual({
        kind: "unavailable",
        query: { cursor: null, limit: 25 },
        canRecordDecision: false,
      });
    },
  );

  it("rejects page rows above the query limit", async () => {
    const row: ConsentRecordView = syntheticRecord();
    expect(
      await queryConsentListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { limit: "1" },
        provider: providerReturning({
          kind: "success",
          page: { items: [row, row], nextCursor: null },
        }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 1 },
      canRecordDecision: false,
    });
  });
});
