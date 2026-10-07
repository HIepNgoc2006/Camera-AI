import { describe, expect, it } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type AuthenticatedSessionSnapshot,
  type PermissionCode,
} from "@/features/auth/domain/route-access";
import { isUiActionVisible } from "@/features/auth/domain/route-access";
import { resolveViolationActionVisibility } from "./action-visibility";
import {
  inactiveViolationCapabilities,
  inactiveViolationReadProvider,
} from "./inactive-runtime";

const NOW = new Date("2026-08-22T12:00:00.000Z");
const CASE_ID = "00000000-0000-4000-8000-000000000073";

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

describe("inactive violation runtime", () => {
  it("keeps read, review, correction, and export capabilities disabled", () => {
    expect(inactiveViolationCapabilities).toEqual({
      readActive: false,
      reviewActive: false,
      correctionActive: false,
      exportActive: false,
    });
  });

  it("fails every checked-in violation list read closed", async () => {
    await expect(
      inactiveViolationReadProvider.readList({
        query: {
          occurredFrom: "2026-08-22",
          occurredTo: "2026-08-22",
          status: null,
          cursor: null,
          limit: 25,
        },
        scope: {
          tenantId: "tenant_synthetic_0073",
          schoolId: "school_synthetic_0073",
          actorId: "actor_synthetic_0073",
        },
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      errorCode: "VIOLATION_RUNTIME_INACTIVE",
    });
  });

  it("fails every checked-in violation detail read closed", async () => {
    await expect(
      inactiveViolationReadProvider.readDetail({
        caseId: CASE_ID,
        scope: {
          tenantId: "tenant_synthetic_0073",
          schoolId: "school_synthetic_0073",
          actorId: "actor_synthetic_0073",
        },
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      errorCode: "VIOLATION_RUNTIME_INACTIVE",
    });
  });
});

describe("resolveViolationActionVisibility", () => {
  it.each([
    {
      permissions: ["violation.view_metadata"] as const,
      capabilities: inactiveViolationCapabilities,
      expected: { canReview: false, canCorrect: false, canExport: false },
    },
    {
      permissions: [
        "violation.view_metadata",
        "violation.review",
        "violation.correct",
        "violation.export",
      ] as const,
      capabilities: inactiveViolationCapabilities,
      expected: { canReview: false, canCorrect: false, canExport: false },
    },
    {
      permissions: [
        "violation.view_metadata",
        "violation.review",
        "violation.correct",
        "violation.export",
      ] as const,
      capabilities: {
        readActive: true,
        reviewActive: true,
        correctionActive: true,
        exportActive: true,
      },
      expected: { canReview: true, canCorrect: true, canExport: true },
    },
    {
      permissions: [
        "violation.review",
        "violation.correct",
        "violation.export",
      ] as const,
      capabilities: {
        readActive: true,
        reviewActive: true,
        correctionActive: true,
        exportActive: true,
      },
      expected: { canReview: false, canCorrect: false, canExport: false },
    },
    {
      permissions: ["violation.view_metadata", "violation.review"] as const,
      capabilities: {
        readActive: true,
        reviewActive: true,
        correctionActive: true,
        exportActive: true,
      },
      expected: { canReview: true, canCorrect: false, canExport: false },
    },
  ])(
    "gates actions by exact permission and active capability %#",
    ({ permissions, capabilities, expected }) => {
      expect(
        resolveViolationActionVisibility({
          session: fakeSession(permissions),
          capabilities,
          now: NOW,
        }),
      ).toEqual(expected);
    },
  );

  it("hides actions for an expired session even with granted permissions", () => {
    const expired = {
      ...fakeSession([
        "violation.view_metadata",
        "violation.review",
        "violation.correct",
        "violation.export",
      ]),
      inactivityExpiresAt: "2026-08-22T10:00:00.000Z",
    };

    expect(
      resolveViolationActionVisibility({
        session: expired,
        capabilities: {
          readActive: true,
          reviewActive: true,
          correctionActive: true,
          exportActive: true,
        },
        now: NOW,
      }),
    ).toEqual({ canReview: false, canCorrect: false, canExport: false });
  });

  it("hides every action for a session snapshot that fails validation", () => {
    expect(
      resolveViolationActionVisibility({
        session: null,
        capabilities: {
          readActive: true,
          reviewActive: true,
          correctionActive: true,
          exportActive: true,
        },
        now: NOW,
      }),
    ).toEqual({ canReview: false, canCorrect: false, canExport: false });
  });

  it("never derives actions from unapproved capability codes", () => {
    const session = fakeSession([
      "violation.view_metadata",
      "violation.review",
    ]);

    expect(
      isUiActionVisible({
        session,
        requiredPermission: "violation.review",
        now: NOW,
      }),
    ).toBe(true);
    expect(
      isUiActionVisible({
        session,
        requiredPermission: "violation.export",
        now: NOW,
      }),
    ).toBe(false);
  });
});
