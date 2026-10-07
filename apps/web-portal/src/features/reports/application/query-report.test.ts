import { describe, expect, it } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type AuthenticatedSessionSnapshot,
  type PermissionCode,
} from "@/features/auth/domain/route-access";
import type { ReportSummary } from "@/features/reports/domain/report-view";

import {
  queryReportListView,
  type ReportReadProvider,
  type ReportRuntimeCapabilities,
} from "./query-report";
import {
  inactiveReportExportProvider,
  type ReportExportSubmitResult,
} from "./submit-report-action";

const NOW = new Date("2026-08-22T12:00:00.000Z");
const CLASS_ID = "00000000-0000-4000-8000-000000000074";
const REPORT_ID = "00000000-0000-4000-8000-000000000075";
const INACTIVE_CAPABILITIES: ReportRuntimeCapabilities = {
  readActive: false,
  exportActive: false,
};
const READ_CAPABILITIES: ReportRuntimeCapabilities = {
  ...INACTIVE_CAPABILITIES,
  readActive: true,
};
const QUERY = {
  day: "2026-08-22",
  classId: null,
  cursor: null,
  limit: 25,
} as const;

function fakeSession(
  permissions: readonly PermissionCode[],
): AuthenticatedSessionSnapshot {
  return {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "authenticated",
    actorId: "actor_synthetic_0074",
    tenantId: "tenant_synthetic_0074",
    schoolId: "school_synthetic_0074",
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

function syntheticSummary(
  overrides: Partial<ReportSummary> = {},
): ReportSummary {
  return {
    reportId: REPORT_ID,
    displayLabel: "Báo cáo thử nghiệm ngày 22/08",
    day: "2026-08-22",
    status: "available",
    updatedAt: "2026-08-22T10:00:00.000Z",
    ...overrides,
  };
}

function explodingProvider(): ReportReadProvider {
  return {
    readList: async () => {
      throw new Error("provider must not be called");
    },
  };
}

describe("queryReportListView", () => {
  it.each([
    null,
    { status: "unauthenticated" },
    {
      ...fakeSession(["report.view_metadata"]),
      policyVersion: "forged_policy",
    },
    {
      ...fakeSession(["report.view_metadata"]),
      absoluteExpiresAt: "2026-08-22T10:00:00.000Z",
    },
  ])(
    "denies invalid session state before provider access %#",
    async (session) => {
      await expect(
        queryReportListView({
          session,
          rawQuery: {},
          provider: explodingProvider(),
          capabilities: READ_CAPABILITIES,
          now: NOW,
        }),
      ).resolves.toEqual({ kind: "denied" });
    },
  );

  it("denies an authenticated actor without the report view permission", async () => {
    await expect(
      queryReportListView({
        session: fakeSession(["violation.view_metadata"]),
        rawQuery: {},
        provider: explodingProvider(),
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "denied" });
  });

  it("returns validation state without provider access for forged scope", async () => {
    await expect(
      queryReportListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: { school_id: CLASS_ID },
        provider: explodingProvider(),
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "validation",
      errorCode: "REPORT_FILTER_INVALID",
    });
  });

  it("returns unavailable without provider access while the runtime is inactive", async () => {
    await expect(
      queryReportListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider: explodingProvider(),
        capabilities: INACTIVE_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: QUERY,
      canExport: false,
    });
  });

  it("derives provider scope only from the authoritative session", async () => {
    const provider: ReportReadProvider = {
      readList: async ({ query, scope }) =>
        scope.actorId === "actor_synthetic_0074" &&
        scope.tenantId === "tenant_synthetic_0074" &&
        scope.schoolId === "school_synthetic_0074" &&
        query.day === "2026-08-22"
          ? {
              kind: "success",
              page: { items: [syntheticSummary()], nextCursor: null },
            }
          : { kind: "denied_or_not_found" },
    };

    await expect(
      queryReportListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toMatchObject({ kind: "success", canExport: false });
  });

  it.each([
    {
      permissions: ["report.view_metadata", "report.export"] as const,
      capabilities: { ...READ_CAPABILITIES, exportActive: true },
      expected: true,
    },
    {
      permissions: ["report.view_metadata", "report.export"] as const,
      capabilities: READ_CAPABILITIES,
      expected: false,
    },
    {
      permissions: ["report.view_metadata"] as const,
      capabilities: { ...READ_CAPABILITIES, exportActive: true },
      expected: false,
    },
    {
      permissions: ["report.export"] as const,
      capabilities: { ...READ_CAPABILITIES, exportActive: true },
      denied: true,
      expected: false,
    },
  ])(
    "gates export visibility by permission plus capability #%#",
    async ({ permissions, capabilities, denied, expected }) => {
      const provider: ReportReadProvider = {
        readList: async () => ({
          kind: "success",
          page: { items: [syntheticSummary()], nextCursor: null },
        }),
      };

      const promise = queryReportListView({
        session: fakeSession(permissions),
        rawQuery: {},
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
        canExport: expected,
      });
    },
  );

  it("maps an authorized empty page to the deterministic empty state", async () => {
    const provider: ReportReadProvider = {
      readList: async () => ({
        kind: "success",
        page: { items: [], nextCursor: null },
      }),
    };

    await expect(
      queryReportListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "empty",
      query: QUERY,
      canExport: false,
    });
  });

  it.each([
    { kind: "denied_or_not_found" as const },
    {
      kind: "unavailable" as const,
      errorCode: "REPORT_UPSTREAM_UNAVAILABLE" as const,
    },
  ])("maps provider result $kind to a stable presentation", async (result) => {
    const provider: ReportReadProvider = {
      readList: async () => result,
    };

    const state = await queryReportListView({
      session: fakeSession(["report.view_metadata"]),
      rawQuery: {},
      provider,
      capabilities: READ_CAPABILITIES,
      now: NOW,
    });

    expect(state).toEqual(
      result.kind === "denied_or_not_found"
        ? { kind: "denied" }
        : { kind: "unavailable", query: QUERY, canExport: false },
    );
  });

  it("does not expose thrown provider error details", async () => {
    const provider: ReportReadProvider = {
      readList: async () => {
        throw new Error("credentialed upstream detail must stay server-side");
      },
    };

    await expect(
      queryReportListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: QUERY,
      canExport: false,
    });
  });

  it.each([
    {
      page: {
        items: [{ ...syntheticSummary(), studentRow: { name: "x" } }],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticSummary({ reportId: "opaque" })],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticSummary({ day: "2026-08-21" })],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticSummary({ displayLabel: " padded " })],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticSummary(), syntheticSummary()],
        nextCursor: null,
      },
    },
    {
      page: {
        items: [syntheticSummary({ status: "STATUS" })],
        nextCursor: null,
      },
    },
    { page: { items: [], nextCursor: "short" } },
    { page: { items: [], nextCursor: null, rowCount: 5 } },
  ])("fails unsafe provider page closed %#", async ({ page }) => {
    const provider = {
      readList: async () => ({ kind: "success", page }),
    } as ReportReadProvider;

    await expect(
      queryReportListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: QUERY,
      canExport: false,
    });
  });
});

describe("inactiveReportExportProvider", () => {
  it("denies every export submission without producing an artifact", async () => {
    await expect(
      inactiveReportExportProvider.submit({
        request: {
          reportId: REPORT_ID,
          format: "csv",
          reason: "management_report",
        },
        scope: {
          tenantId: "tenant_synthetic_0074",
          schoolId: "school_synthetic_0074",
          actorId: "actor_synthetic_0074",
        },
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      errorCode: "REPORT_EXPORT_INACTIVE",
    });
  });

  it("never exposes a submit success shape to compose against", async () => {
    const result: ReportExportSubmitResult =
      await inactiveReportExportProvider.submit({
        request: {
          reportId: REPORT_ID,
          format: "xlsx",
          reason: "violation_review",
        },
        scope: {
          tenantId: "t",
          schoolId: "s",
          actorId: "a",
        },
      });

    expect("exportRef" in result).toBe(false);
    expect("job" in result).toBe(false);
  });
});
