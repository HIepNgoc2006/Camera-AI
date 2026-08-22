import { describe, expect, it } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type AuthenticatedSessionSnapshot,
  type PermissionCode,
} from "@/features/auth/domain/route-access";
import type { AttendanceRecord } from "@/features/attendance/domain/attendance-view";

import {
  queryAttendanceView,
  type AttendanceReadProvider,
  type AttendanceRuntimeCapabilities,
} from "./query-attendance";

const NOW = new Date("2026-08-22T12:00:00.000Z");
const CLASS_ID = "00000000-0000-4000-8000-000000000072";
const RECORD_ID = "00000000-0000-4000-8000-000000000073";
const INACTIVE_CAPABILITIES: AttendanceRuntimeCapabilities = {
  readActive: false,
  correctionActive: false,
  linkedChildScopeActive: false,
};
const READ_CAPABILITIES: AttendanceRuntimeCapabilities = {
  ...INACTIVE_CAPABILITIES,
  readActive: true,
};

function fakeSession(
  permissions: readonly PermissionCode[],
): AuthenticatedSessionSnapshot {
  return {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "authenticated",
    actorId: "actor_synthetic_0072",
    tenantId: "tenant_synthetic_0072",
    schoolId: "school_synthetic_0072",
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

function syntheticRecord(
  overrides: Partial<AttendanceRecord> = {},
): AttendanceRecord {
  return {
    recordId: RECORD_ID,
    displayLabel: "Học sinh thử nghiệm 01",
    classId: CLASS_ID,
    classLabel: "Lớp thử nghiệm 10A",
    day: "2026-08-22",
    status: "present",
    updatedAt: "2026-08-22T10:00:00.000Z",
    ...overrides,
  };
}

function explodingProvider(): AttendanceReadProvider {
  return {
    read: async () => {
      throw new Error("provider must not be called");
    },
  };
}

describe("queryAttendanceView", () => {
  it.each([
    null,
    { status: "unauthenticated" },
    {
      ...fakeSession(["attendance.view_metadata"]),
      policyVersion: "forged_policy",
    },
  ])(
    "denies invalid session state before provider access %#",
    async (session) => {
      await expect(
        queryAttendanceView({
          session,
          rawQuery: {},
          provider: explodingProvider(),
          capabilities: READ_CAPABILITIES,
          now: NOW,
        }),
      ).resolves.toEqual({ kind: "denied" });
    },
  );

  it("denies an authenticated actor without attendance view permission", async () => {
    await expect(
      queryAttendanceView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider: explodingProvider(),
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({ kind: "denied" });
  });

  it("returns validation state without provider access for forged scope", async () => {
    await expect(
      queryAttendanceView({
        session: fakeSession(["attendance.view_metadata"]),
        rawQuery: { school_id: "00000000-0000-4000-8000-000000000099" },
        provider: explodingProvider(),
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "validation",
      errorCode: "ATTENDANCE_FILTER_INVALID",
    });
  });

  it("returns unavailable without provider access while the runtime is inactive", async () => {
    await expect(
      queryAttendanceView({
        session: fakeSession(["attendance.view_metadata"]),
        rawQuery: {},
        provider: explodingProvider(),
        capabilities: INACTIVE_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: {
        day: "2026-08-22",
        classId: null,
        cursor: null,
        limit: 25,
      },
      canCorrect: false,
    });
  });

  it("derives provider scope only from the authoritative session", async () => {
    const provider: AttendanceReadProvider = {
      read: async ({ query, scope }) =>
        scope.actorId === "actor_synthetic_0072" &&
        scope.tenantId === "tenant_synthetic_0072" &&
        scope.schoolId === "school_synthetic_0072" &&
        query.classId === CLASS_ID
          ? {
              kind: "success",
              page: { records: [syntheticRecord()], nextCursor: null },
            }
          : { kind: "denied_or_not_found" },
    };

    await expect(
      queryAttendanceView({
        session: fakeSession(["attendance.view_metadata"]),
        rawQuery: { classId: CLASS_ID },
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toMatchObject({ kind: "success", canCorrect: false });
  });

  it("maps an authorized empty page to the deterministic empty state", async () => {
    const provider: AttendanceReadProvider = {
      read: async () => ({
        kind: "success",
        page: { records: [], nextCursor: null },
      }),
    };

    await expect(
      queryAttendanceView({
        session: fakeSession(["attendance.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "empty",
      query: {
        day: "2026-08-22",
        classId: null,
        cursor: null,
        limit: 25,
      },
      canCorrect: false,
    });
  });

  it.each([
    {
      permissions: ["attendance.view_metadata", "attendance.correct"] as const,
      capabilities: {
        ...READ_CAPABILITIES,
        correctionActive: false,
      },
      expected: false,
    },
    {
      permissions: ["attendance.view_metadata"] as const,
      capabilities: {
        ...READ_CAPABILITIES,
        correctionActive: true,
      },
      expected: false,
    },
    {
      permissions: ["attendance.view_metadata", "attendance.correct"] as const,
      capabilities: {
        ...READ_CAPABILITIES,
        correctionActive: true,
      },
      expected: true,
    },
  ])(
    "sets correction visibility to $expected only from permission plus capability",
    async ({ permissions, capabilities, expected }) => {
      const provider: AttendanceReadProvider = {
        read: async () => ({
          kind: "success",
          page: { records: [syntheticRecord()], nextCursor: null },
        }),
      };

      await expect(
        queryAttendanceView({
          session: fakeSession(permissions),
          rawQuery: {},
          provider,
          capabilities,
          now: NOW,
        }),
      ).resolves.toMatchObject({ kind: "success", canCorrect: expected });
    },
  );

  it.each([
    { kind: "denied_or_not_found" as const },
    {
      kind: "unavailable" as const,
      errorCode: "ATTENDANCE_UPSTREAM_UNAVAILABLE" as const,
    },
  ])("maps provider result $kind to a stable presentation", async (result) => {
    const provider: AttendanceReadProvider = {
      read: async () => result,
    };

    const state = await queryAttendanceView({
      session: fakeSession(["attendance.view_metadata"]),
      rawQuery: {},
      provider,
      capabilities: READ_CAPABILITIES,
      now: NOW,
    });

    expect(state).toEqual(
      result.kind === "denied_or_not_found"
        ? { kind: "denied" }
        : {
            kind: "unavailable",
            query: {
              day: "2026-08-22",
              classId: null,
              cursor: null,
              limit: 25,
            },
            canCorrect: false,
          },
    );
  });

  it("does not expose thrown provider error details", async () => {
    const provider: AttendanceReadProvider = {
      read: async () => {
        throw new Error("credentialed upstream detail must stay server-side");
      },
    };

    await expect(
      queryAttendanceView({
        session: fakeSession(["attendance.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: {
        day: "2026-08-22",
        classId: null,
        cursor: null,
        limit: 25,
      },
      canCorrect: false,
    });
  });

  it.each([
    {
      records: [{ ...syntheticRecord(), faceEmbedding: "forbidden" }],
      nextCursor: null,
    },
    {
      records: [syntheticRecord({ day: "2026-08-21" })],
      nextCursor: null,
    },
    {
      records: [syntheticRecord({ classId: "not-a-uuid" })],
      nextCursor: null,
    },
    {
      records: [syntheticRecord({ displayLabel: " label with padding " })],
      nextCursor: null,
    },
  ])("fails unsafe provider page closed %#", async (page) => {
    const provider = {
      read: async () => ({ kind: "success", page }),
    } as AttendanceReadProvider;

    await expect(
      queryAttendanceView({
        session: fakeSession(["attendance.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: READ_CAPABILITIES,
        now: NOW,
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      query: {
        day: "2026-08-22",
        classId: null,
        cursor: null,
        limit: 25,
      },
      canCorrect: false,
    });
  });
});
