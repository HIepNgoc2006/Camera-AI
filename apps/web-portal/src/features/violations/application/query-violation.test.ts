import { describe, expect, it } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type AuthenticatedSessionSnapshot,
  type PermissionCode,
} from "@/features/auth/domain/route-access";
import type {
  ViolationDetail,
  ViolationListItem,
} from "@/features/violations/domain/violation-view";

import {
  queryViolationDetailView,
  queryViolationListView,
  type ViolationReadProvider,
  type ViolationRuntimeCapabilities,
} from "./query-violation";

const NOW = new Date("2026-08-22T12:00:00.000Z");
const CASE_ID = "00000000-0000-4000-8000-000000000073";
const SECOND_CASE_ID = "00000000-0000-4000-8000-000000000074";
const INACTIVE_CAPABILITIES: ViolationRuntimeCapabilities = {
  readActive: false,
  reviewActive: false,
  correctionActive: false,
  exportActive: false,
};
const READ_CAPABILITIES: ViolationRuntimeCapabilities = {
  ...INACTIVE_CAPABILITIES,
  readActive: true,
};
const QUERY = {
  occurredFrom: "2026-08-20",
  occurredTo: "2026-08-21",
  status: null,
  cursor: null,
  limit: 25,
} as const;

function fakeSession(
  permissions: readonly PermissionCode[],
): AuthenticatedSessionSnapshot {
  return {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "authenticated",
    actorId: "actor_synthetic_0073",
    tenantId: "tenant_synthetic_0073",
    schoolId: "school_synthetic_0073",
    mfaState: "verified",
    issuedAt: "2026-08-22T08:00:00.000Z",
    warningStartsAt: "2026-08-22T15:00:00.000Z",
    inactivityExpiresAt: "2026-08-22T16:00:00.000Z",
    absoluteExpiresAt: "2026-08-22T20:00:00.000Z",
    authorization: {
      policyVersion: AUTHORIZATION_POLICY_VERSION,
      permissions,
    },
  };
}

function syntheticListItem(
  overrides: Partial<ViolationListItem> = {},
): ViolationListItem {
  return {
    caseId: CASE_ID,
    caseRef: "case_fake_0001",
    category: "suspected_littering",
    occurredAt: "2026-08-21T10:00:00.000Z",
    reviewStatus: "pending_review",
    appealState: "not_appealed",
    correctionState: "not_corrected",
    legalHoldState: "none",
    ...overrides,
  };
}

function syntheticDetail(
  overrides: Partial<ViolationDetail> = {},
): ViolationDetail {
  return {
    ...syntheticListItem(),
    updatedAt: "2026-08-21T11:00:00.000Z",
    ...overrides,
  };
}

function explodingProvider(): ViolationReadProvider {
  return {
    readList: async () => {
      throw new Error("provider list must not be called");
    },
    readDetail: async () => {
      throw new Error("provider detail must not be called");
    },
  };
}

describe("queryViolationListView", () => {
  it("accepts provider items matching the requested confirmed status", async () => {
    const result = await queryViolationListView({
      session: fakeSession(["violation.view_metadata"]),
      rawQuery: {
        occurredFrom: "2026-08-20",
        occurredTo: "2026-08-21",
        status: "confirmed",
      },
      provider: {
        readList: async () => ({
          kind: "success",
          page: {
            items: [syntheticListItem({ reviewStatus: "confirmed" })],
            nextCursor: null,
          },
        }),
        readDetail: explodingProvider().readDetail,
      },
      capabilities: READ_CAPABILITIES,
      now: NOW,
    });
    expect(result.kind).toBe("success");
  });
  it.each(["constructor", "toString", "__proto__", "hasOwnProperty"])(
    "rejects inherited provider status without a filter (%s)",
    async (status) => {
      const result = await queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        provider: {
          readList: async () => ({
            kind: "success",
            page: {
              items: [
                {
                  ...syntheticListItem(),
                  reviewStatus: status,
                } as ViolationListItem,
              ],
              nextCursor: null,
            },
          }),
          readDetail: explodingProvider().readDetail,
        },
        capabilities: READ_CAPABILITIES,
        now: NOW,
      });
      expect(result.kind).toBe("unavailable");
    },
  );

  it.each(["constructor", "toString", "__proto__", "hasOwnProperty"])(
    "rejects inherited detail status (%s)",
    async (status) => {
      const result = await queryViolationDetailView({
        session: fakeSession(["violation.view_metadata"]),
        caseId: CASE_ID,
        provider: {
          readList: explodingProvider().readList,
          readDetail: async () => ({
            kind: "success",
            detail: {
              ...syntheticDetail(),
              reviewStatus: status,
            } as ViolationDetail,
          }),
        },
        capabilities: READ_CAPABILITIES,
        now: NOW,
      });
      expect(result.kind).toBe("unavailable");
    },
  );
  it.each(["constructor", "toString", "__proto__", "hasOwnProperty", "closed"])(
    "rejects provider status outside requested confirmed status (%s)",
    async (status) => {
      const item = { ...syntheticListItem(), reviewStatus: status };
      const result = await queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: {
          occurredFrom: "2026-08-20",
          occurredTo: "2026-08-21",
          status: "confirmed",
        },
        provider: {
          readList: async () => ({
            kind: "success",
            page: { items: [item as ViolationListItem], nextCursor: null },
          }),
          readDetail: explodingProvider().readDetail,
        },
        capabilities: READ_CAPABILITIES,
        now: NOW,
      });
      expect(result.kind).toBe("unavailable");
    },
  );
  it.each([
    null,
    { status: "unauthenticated" },
    {
      ...fakeSession(["violation.view_metadata"]),
      policyVersion: "forged_policy",
    },
    {
      ...fakeSession(["violation.view_metadata"]),
      inactivityExpiresAt: "2026-08-22T10:00:00.000Z",
    },
  ])(
    "denies invalid session state before provider access %#",
    async (session) => {
      await expect(
        queryViolationListView({
          session,
          rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
          provider: explodingProvider(),
          capabilities: READ_CAPABILITIES,
          now: NOW,
        }),
      ).resolves.toEqual({ kind: "denied" });
    },
  );

  it("denies an authenticated actor without the exact violation view permission", async () => {
    await expect(
      queryViolationListView({
        session: fakeSession(["attendance.view_metadata"]),
        rawQuery: {},
        provider: explodingProvider(),
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "denied" });
  });

  it("returns validation state without provider access for forged scope", async () => {
    await expect(
      queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: { school_id: "00000000-0000-4000-8000-000000000099" },
        provider: explodingProvider(),
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "validation",
      errorCode: "VIOLATION_FILTER_INVALID",
    });
  });

  it("returns unavailable without provider access while the runtime is inactive", async () => {
    await expect(
      queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        provider: explodingProvider(),
        capabilities: INACTIVE_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: QUERY,
      actions: {
        canReview: false,
        canCorrect: false,
        canExport: false,
      },
    });
  });

  it("derives provider scope only from the authoritative session", async () => {
    const provider: ViolationReadProvider = {
      readList: async ({ query, scope }) =>
        scope.actorId === "actor_synthetic_0073" &&
        scope.tenantId === "tenant_synthetic_0073" &&
        scope.schoolId === "school_synthetic_0073" &&
        query.occurredFrom === "2026-08-20"
          ? {
              kind: "success",
              page: { items: [syntheticListItem()], nextCursor: null },
            }
          : { kind: "denied_or_not_found" },
      readDetail: explodingProvider().readDetail,
    };

    await expect(
      queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toMatchObject({ kind: "success" });
  });

  it("maps an authorized empty page to the deterministic empty state", async () => {
    const provider: ViolationReadProvider = {
      readList: async () => ({
        kind: "success",
        page: { items: [], nextCursor: null },
      }),
      readDetail: explodingProvider().readDetail,
    };

    await expect(
      queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "empty",
      query: { ...QUERY, occurredFrom: "2026-08-22", occurredTo: "2026-08-22" },
      actions: { canReview: false, canCorrect: false, canExport: false },
    });
  });

  it.each([
    {
      permissions: ["violation.view_metadata", "violation.review"] as const,
      capabilities: { ...READ_CAPABILITIES, reviewActive: true },
      expectedReview: true,
      expectedCorrect: false,
      expectedExport: false,
    },
    {
      permissions: ["violation.view_metadata", "violation.review"] as const,
      capabilities: { ...READ_CAPABILITIES, reviewActive: false },
      expectedReview: false,
      expectedCorrect: false,
      expectedExport: false,
    },
    {
      permissions: ["violation.review"] as const,
      capabilities: { ...READ_CAPABILITIES, reviewActive: true },
      denied: true,
      expectedReview: false,
      expectedCorrect: false,
      expectedExport: false,
    },
    {
      permissions: ["violation.view_metadata", "violation.correct"] as const,
      capabilities: { ...READ_CAPABILITIES, correctionActive: true },
      expectedReview: false,
      expectedCorrect: true,
      expectedExport: false,
    },
    {
      permissions: ["violation.view_metadata", "violation.export"] as const,
      capabilities: { ...READ_CAPABILITIES, exportActive: true },
      expectedReview: false,
      expectedCorrect: false,
      expectedExport: true,
    },
  ])(
    "resolves actions from permission plus active capability #$#",
    async ({
      permissions,
      capabilities,
      denied,
      expectedReview,
      expectedCorrect,
      expectedExport,
    }) => {
      const provider: ViolationReadProvider = {
        readList: async () => ({
          kind: "success",
          page: { items: [syntheticListItem()], nextCursor: null },
        }),
        readDetail: explodingProvider().readDetail,
      };

      const promise = queryViolationListView({
        session: fakeSession(permissions),
        rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        provider,
        capabilities,
        now: NOW,
      });

      if (denied) {
        await expect(promise).resolves.toEqual({ kind: "denied" });
        return;
      }
      await expect(promise).resolves.toMatchObject({
        kind: "success",
        actions: {
          canReview: expectedReview,
          canCorrect: expectedCorrect,
          canExport: expectedExport,
        },
      });
    },
  );

  it.each([
    { kind: "denied_or_not_found" as const },
    {
      kind: "unavailable" as const,
      errorCode: "VIOLATION_UPSTREAM_UNAVAILABLE" as const,
    },
  ])(
    "maps provider list result $kind to a stable presentation",
    async (result) => {
      const provider: ViolationReadProvider = {
        readList: async () => result,
        readDetail: explodingProvider().readDetail,
      };

      const state = await queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      });

      expect(state).toEqual(
        result.kind === "denied_or_not_found"
          ? { kind: "denied" }
          : {
              kind: "unavailable",
              query: QUERY,
              actions: {
                canReview: false,
                canCorrect: false,
                canExport: false,
              },
            },
      );
    },
  );

  it("does not expose thrown provider error details", async () => {
    const provider: ViolationReadProvider = {
      readList: async () => {
        throw new Error("credentialed upstream detail must stay server-side");
      },
      readDetail: explodingProvider().readDetail,
    };

    await expect(
      queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: QUERY,
      actions: { canReview: false, canCorrect: false, canExport: false },
    });
  });

  it.each([
    {
      page: {
        items: [{ ...syntheticListItem(), faceEmbedding: "forbidden" }],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticListItem({ caseId: "opaque-ref" })],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [
          syntheticListItem({
            reviewStatus: "appealed",
          } as unknown as Partial<ViolationListItem>),
        ],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [
          syntheticListItem({
            legalHoldState: "ACTIVE",
          } as unknown as Partial<ViolationListItem>),
        ],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticListItem({ occurredAt: "2026-08-19T10:00:00.000Z" })],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticListItem(), syntheticListItem()],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticListItem({ caseRef: "https://evil.example/case" })],
        nextCursor: null,
      },
    },
    { page: { items: [syntheticListItem()], nextCursor: "short" } },
    { page: { items: [], nextCursor: null, total: 5 } },
  ])("fails unsafe provider list page closed %#", async ({ page }) => {
    const provider = {
      readList: async () => ({ kind: "success", page }),
      readDetail: explodingProvider().readDetail,
    } as ViolationReadProvider;

    await expect(
      queryViolationListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: QUERY,
      actions: { canReview: false, canCorrect: false, canExport: false },
    });
  });
});

describe("queryViolationDetailView", () => {
  it("denies invalid session before provider access", async () => {
    await expect(
      queryViolationDetailView({
        session: null,
        caseId: CASE_ID,
        provider: explodingProvider(),
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "denied" });
  });

  it.each([
    "",
    "opaque-case-ref",
    "00000000-0000-4000-8000-000000000073;DROP",
    "0000000a-0000-4000-8000-00000000007G",
    `${CASE_ID}-extra`,
  ])(
    "treats malformed direct case id %# as non-enumerating not found",
    async (caseId) => {
      await expect(
        queryViolationDetailView({
          session: fakeSession(["violation.view_metadata"]),
          caseId,
          provider: explodingProvider(),
          capabilities: READ_CAPABILITIES,
          now: NOW,
        }),
      ).resolves.toEqual({ kind: "not_found" });
    },
  );

  it("returns unavailable while the runtime is inactive", async () => {
    await expect(
      queryViolationDetailView({
        session: fakeSession(["violation.view_metadata"]),
        caseId: CASE_ID,
        provider: explodingProvider(),
        capabilities: INACTIVE_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "unavailable" });
  });

  it("maps provider denial and upstream failure to separate stable states", async () => {
    const deniedProvider: ViolationReadProvider = {
      readList: explodingProvider().readList,
      readDetail: async () => ({ kind: "denied_or_not_found" }),
    };
    await expect(
      queryViolationDetailView({
        session: fakeSession(["violation.view_metadata"]),
        caseId: CASE_ID,
        provider: deniedProvider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "not_found" });

    const unavailableProvider: ViolationReadProvider = {
      readList: explodingProvider().readList,
      readDetail: async () => ({
        kind: "unavailable",
        errorCode: "VIOLATION_UPSTREAM_UNAVAILABLE",
      }),
    };
    await expect(
      queryViolationDetailView({
        session: fakeSession(["violation.view_metadata"]),
        caseId: CASE_ID,
        provider: unavailableProvider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "unavailable" });
  });

  it.each([
    {
      detail: syntheticDetail({
        faceEmbedding: "forbidden",
      } as unknown as Partial<ViolationDetail>),
    },
    { detail: syntheticDetail({ updatedAt: "2026-08-20T11:00:00.000Z" }) },
    { detail: syntheticDetail({ updatedAt: "2026-08-21T11:00:03Z" }) },
    {
      detail: syntheticDetail({
        appealState: "rejected",
      } as unknown as Partial<ViolationDetail>),
    },
    { detail: syntheticDetail({ caseRef: "../object-key" }) },
  ])("fails unsafe provider detail closed %#", async ({ detail }) => {
    const provider = {
      readList: explodingProvider().readList,
      readDetail: async () => ({ kind: "success", detail }),
    } as unknown as ViolationReadProvider;

    await expect(
      queryViolationDetailView({
        session: fakeSession(["violation.view_metadata"]),
        caseId: CASE_ID,
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "unavailable" });
  });

  it("returns the sanitized detail for an authorized reader", async () => {
    const provider: ViolationReadProvider = {
      readList: explodingProvider().readList,
      readDetail: async ({ caseId, scope }) =>
        caseId === CASE_ID && scope.schoolId === "school_synthetic_0073"
          ? { kind: "success", detail: syntheticDetail() }
          : { kind: "denied_or_not_found" },
    };

    await expect(
      queryViolationDetailView({
        session: fakeSession(["violation.view_metadata"]),
        caseId: CASE_ID,
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "success", detail: syntheticDetail() });
  });

  it("rejects a detail whose case id differs from the requested one", async () => {
    const provider: ViolationReadProvider = {
      readList: explodingProvider().readList,
      readDetail: async () => ({
        kind: "success",
        detail: syntheticDetail({ caseId: SECOND_CASE_ID }),
      }),
    };

    await expect(
      queryViolationDetailView({
        session: fakeSession(["violation.view_metadata"]),
        caseId: CASE_ID,
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "unavailable" });
  });
});
