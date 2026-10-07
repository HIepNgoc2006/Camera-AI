import { describe, expect, it, vi } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type PermissionCode,
  type SessionSnapshot,
} from "@/features/auth/domain/route-access";
import type { AccessQuery } from "@/features/access/domain/access-view";
import type { RoleAssignmentView } from "@/features/access/domain/access-view";
import type {
  AccessReadProvider,
  AccessReadProviderResult,
  AccessRuntimeCapabilities,
  RoleAssignmentPage,
} from "./query-access";
import { queryAccessListView } from "./query-access";

const NOW = new Date("2026-10-07T12:00:00.000Z");
const ASSIGNMENT_ID = "00000000-0000-4000-8000-00000000007a";

const INACTIVE: AccessRuntimeCapabilities = {
  readActive: false,
  mutationActive: false,
};

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

function syntheticPage(): RoleAssignmentPage {
  return {
    items: [
      {
        assignmentId: ASSIGNMENT_ID,
        subjectActorRef: "actor_test_002",
        displayLabel: "Quản trị trường — thử nghiệm",
        roleCode: "school_admin",
        scopeSchoolId: "school_test_001",
        validFrom: "2026-09-01T00:00:00.000Z",
        validUntil: null,
        revokedAt: null,
        status: "active",
        version: 2,
      },
    ],
    nextCursor: null,
  };
}

function providerReturning(
  result: AccessReadProviderResult,
): AccessReadProvider {
  return { readList: vi.fn().mockResolvedValue(result) };
}

const VIEW_ONLY: readonly PermissionCode[] = ["role_assignment.view_metadata"];
const VIEW_AND_CORRECT: readonly PermissionCode[] = [
  "role_assignment.view_metadata",
  "role_assignment.correct",
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
        await queryAccessListView({
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
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider,
        capabilities: { readActive: true, mutationActive: true },
        now: new Date("2026-10-09T00:00:00.000Z"),
      }),
    ).toEqual({ kind: "denied" });
    expect(provider.readList).not.toHaveBeenCalled();
  });

  it("denies the view permission before any provider call", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryAccessListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "denied" });
    expect(provider.readList).not.toHaveBeenCalled();
  });

  it("denies a session whose MFA is not verified", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY, { mfaState: "not_required" }),
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
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { tenantId: "tenant_evil" },
        provider,
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "validation", errorCode: "ACCESS_FILTER_INVALID" });
    expect(provider.readList).not.toHaveBeenCalled();
  });

  it("reports validation failure for a malformed limit", async () => {
    expect(
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { limit: "1000" },
        provider: providerReturning({ kind: "success", page: syntheticPage() }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "validation", errorCode: "ACCESS_FILTER_INVALID" });
  });
});

describe("runtime capabilities", () => {
  it("returns unavailable without any provider call when read is inactive", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider,
        capabilities: INACTIVE,
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
      canProposeChange: false,
    });
    expect(provider.readList).not.toHaveBeenCalled();
  });
});

describe("authorized provider reads", () => {
  it("narrows the authoritative scope from the server session only", async () => {
    const readList = vi
      .fn()
      .mockResolvedValue({ kind: "success", page: syntheticPage() });
    await queryAccessListView({
      session: fakeSession(VIEW_AND_CORRECT),
      rawQuery: { limit: "50" },
      provider: { readList },
      capabilities: { readActive: true, mutationActive: true },
      now: NOW,
    });

    expect(readList).toHaveBeenCalledWith({
      query: { cursor: null, limit: 50 } satisfies AccessQuery,
      scope: {
        tenantId: "tenant_test_001",
        schoolId: "school_test_001",
        actorId: "actor_test_001",
      },
    });
  });

  it("maps provider denial to the public denied state", async () => {
    expect(
      await queryAccessListView({
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
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: { readList },
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
      canProposeChange: false,
    });
  });

  it("maps an invalid provider shape to sanitized unavailable", async () => {
    expect(
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: { readList: vi.fn().mockResolvedValue({ kind: "boom" }) },
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
      canProposeChange: false,
    });
  });

  it("returns empty for a page with no rows", async () => {
    expect(
      await queryAccessListView({
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
      canProposeChange: false,
    });
  });

  it("returns the decoded page for an authorized actor", async () => {
    expect(
      await queryAccessListView({
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
      canProposeChange: true,
    });
  });

  it("keeps propose-change hidden without the correct permission", async () => {
    expect(
      await queryAccessListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: syntheticPage(),
        }),
        capabilities: { readActive: true, mutationActive: true },
        now: NOW,
      }),
    ).toMatchObject({ canProposeChange: false });
  });

  it("keeps propose-change hidden when the mutation runtime is inactive", async () => {
    expect(
      await queryAccessListView({
        session: fakeSession(VIEW_AND_CORRECT),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: syntheticPage(),
        }),
        capabilities: { readActive: true, mutationActive: false },
        now: NOW,
      }),
    ).toMatchObject({ canProposeChange: false });
  });
});

describe("provider payload safety", () => {
  type UnsafeOverride = Partial<Omit<RoleAssignmentView, "status">> & {
    status?: string;
  };
  it.each([
    {
      case: "cross-school scope leak",
      override: { scopeSchoolId: "school_other_002" },
    },
    {
      case: "credential material",
      override: {},
      extra: { password_hash: "argon2$canary" },
    },
    {
      case: "duplicate assignment id",
      override: {},
      duplicate: true,
    },
    {
      case: "unsafe role code",
      override: { roleCode: "ROLE; DROP" },
    },
    {
      case: "non-canonical instant",
      override: { validFrom: "2026-09-01" },
    },
    {
      case: "invalid version",
      override: { version: 0 },
    },
    {
      case: "unknown status",
      override: { status: "superuser" } satisfies UnsafeOverride,
    },
  ] as ReadonlyArray<{
    case: string;
    override: UnsafeOverride;
    extra?: Record<string, unknown>;
    duplicate?: boolean;
  }>)(
    "rejects unsafe payload: $case",
    async ({ override, extra, duplicate }) => {
      const row: RoleAssignmentView = {
        assignmentId: ASSIGNMENT_ID,
        subjectActorRef: "actor_test_002",
        displayLabel: "Quản trị trường — thử nghiệm",
        roleCode: "school_admin",
        scopeSchoolId: "school_test_001",
        validFrom: "2026-09-01T00:00:00.000Z",
        validUntil: null,
        revokedAt: null,
        status: "active",
        version: 2,
        ...override,
        ...(extra ?? {}),
      } as RoleAssignmentView;
      const items = duplicate ? [row, row] : [row];
      const result: AccessReadProviderResult = {
        kind: "success",
        page: { items, nextCursor: null },
      };

      expect(
        await queryAccessListView({
          session: fakeSession(VIEW_ONLY),
          rawQuery: {},
          provider: providerReturning(result),
          capabilities: { readActive: true, mutationActive: true },
          now: NOW,
        }),
      ).toEqual({
        kind: "unavailable",
        query: { cursor: null, limit: 25 },
        canProposeChange: false,
      });
    },
  );

  it("rejects page rows above the query limit", async () => {
    const row: RoleAssignmentView = {
      assignmentId: ASSIGNMENT_ID,
      subjectActorRef: "actor_test_002",
      displayLabel: "Quản trị trường — thử nghiệm",
      roleCode: "school_admin",
      scopeSchoolId: "school_test_001",
      validFrom: "2026-09-01T00:00:00.000Z",
      validUntil: null,
      revokedAt: null,
      status: "active",
      version: 2,
    };
    expect(
      await queryAccessListView({
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
      canProposeChange: false,
    });
  });
});
