import { describe, expect, it } from "vitest";

import {
  evaluateLogoutResponse,
  evaluateBffSessionSnapshot,
  toRouteSession,
  type BffSessionEvaluation,
} from "./bff-session";
import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type AuthenticatedSessionSnapshot,
} from "./route-access";

const NOW = new Date("2026-08-02T03:00:00.000Z");

describe("logout response", () => {
  const confirmed = {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "unauthenticated",
    errorCode: "AUTH_REQUIRED",
    redirectTo: "/login",
  };
  it("accepts completion only for a successful matching response", () => {
    expect(evaluateLogoutResponse(true, confirmed)).toBe("confirmed");
  });
  it.each([
    null,
    {},
    { ...confirmed, status: "authenticated" },
    { ...confirmed, policyVersion: "unknown" },
    { ...confirmed, redirectTo: "https://evil.invalid" },
  ])("rejects misleading or malformed response %j", (value) => {
    expect(evaluateLogoutResponse(true, value)).toBe("unconfirmed");
  });
  it("does not turn an HTTP failure with a redirect into success", () => {
    expect(evaluateLogoutResponse(false, confirmed)).toBe("unconfirmed");
  });
  it("requires reauthentication after local session loss without remote confirmation", () => {
    expect(
      evaluateLogoutResponse(false, {
        policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
        status: "unavailable",
        errorCode: "SESSION_UNAVAILABLE",
      }),
    ).toBe("reauthentication_required");
    expect(
      evaluateLogoutResponse(false, {
        policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
        status: "unauthenticated",
        errorCode: "REQUEST_REJECTED",
      }),
    ).toBe("reauthentication_required");
  });
});

function validAuthenticatedSnapshot(): AuthenticatedSessionSnapshot {
  return {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "authenticated",
    actorId: "actor_test_001",
    tenantId: "tenant_test_001",
    schoolId: "school_test_001",
    mfaState: "verified",
    issuedAt: "2026-08-02T02:00:00.000Z",
    warningStartsAt: "2026-08-02T03:30:00.000Z",
    inactivityExpiresAt: "2026-08-02T04:00:00.000Z",
    absoluteExpiresAt: "2026-08-02T05:00:00.000Z",
    authorization: {
      policyVersion: AUTHORIZATION_POLICY_VERSION,
      permissions: ["attendance.view_metadata"],
    },
  };
}

describe("evaluateBffSessionSnapshot", () => {
  it("accepts only the exact server snapshot versions and active timeline", () => {
    expect(
      evaluateBffSessionSnapshot(validAuthenticatedSnapshot(), NOW),
    ).toEqual({
      kind: "authenticated",
      session: validAuthenticatedSnapshot(),
    });
  });

  it.each([
    ["unauthenticated", { kind: "login_required", state: "unauthenticated" }],
    ["expired", { kind: "login_required", state: "expired" }],
    ["revoked", { kind: "login_required", state: "revoked" }],
    ["mfa_required", { kind: "mfa_challenge", state: "mfa_required" }],
    ["mfa_failed", { kind: "mfa_challenge", state: "mfa_failed" }],
    ["unavailable", { kind: "unavailable" }],
    ["malformed", { kind: "malformed" }],
  ] as const)(
    "maps %s without exposing internal detail",
    (status, expected) => {
      expect(
        evaluateBffSessionSnapshot(
          { policyVersion: WEB_BFF_SESSION_POLICY_VERSION, status },
          NOW,
        ),
      ).toEqual(expected);
    },
  );

  it("treats an authenticated snapshot at either expiry boundary as expired", () => {
    const snapshot = {
      ...validAuthenticatedSnapshot(),
      warningStartsAt: "2026-08-02T02:30:00.000Z",
      inactivityExpiresAt: NOW.toISOString(),
    };

    expect(evaluateBffSessionSnapshot(snapshot, NOW)).toEqual({
      kind: "login_required",
      state: "expired",
    });
  });

  it.each([
    { ...validAuthenticatedSnapshot(), role: "admin" },
    {
      ...validAuthenticatedSnapshot(),
      authorization: {
        policyVersion: AUTHORIZATION_POLICY_VERSION,
        permissions: ["unknown.permission"],
      },
    },
  ])(
    "keeps an expired-looking client-augmented snapshot malformed",
    (invalidSnapshot) => {
      expect(
        evaluateBffSessionSnapshot(
          {
            ...invalidSnapshot,
            warningStartsAt: "2026-08-02T02:30:00.000Z",
            inactivityExpiresAt: NOW.toISOString(),
          },
          NOW,
        ),
      ).toEqual({ kind: "malformed" });
    },
  );

  it("rejects an invalid evaluation clock instead of inferring expiry", () => {
    expect(
      evaluateBffSessionSnapshot(validAuthenticatedSnapshot(), new Date(NaN)),
    ).toEqual({ kind: "malformed" });
  });

  it.each([
    {},
    { policyVersion: "unknown", status: "authenticated" },
    {
      ...validAuthenticatedSnapshot(),
      authorization: {
        policyVersion: AUTHORIZATION_POLICY_VERSION,
        permissions: ["unknown.permission"],
      },
    },
    { ...validAuthenticatedSnapshot(), role: "admin" },
    { ...validAuthenticatedSnapshot(), tenantId: " tenant_test_001" },
    { ...validAuthenticatedSnapshot(), warningStartsAt: "not-an-instant" },
  ])("fails malformed or client-augmented state closed", (snapshot) => {
    expect(evaluateBffSessionSnapshot(snapshot, NOW)).toEqual({
      kind: "malformed",
    });
  });
});

describe("toRouteSession", () => {
  it("passes only an authenticated validated snapshot to the route guard", () => {
    const evaluation = evaluateBffSessionSnapshot(
      validAuthenticatedSnapshot(),
      NOW,
    );

    expect(toRouteSession(evaluation)).toEqual(validAuthenticatedSnapshot());
  });

  it.each([
    { kind: "login_required", state: "revoked" },
    { kind: "mfa_challenge", state: "mfa_required" },
  ] satisfies readonly BffSessionEvaluation[])(
    "maps login and MFA states to unauthenticated route state",
    (evaluation) => {
      expect(toRouteSession(evaluation)).toEqual({ status: "unauthenticated" });
    },
  );

  it.each([
    { kind: "unavailable" },
    { kind: "malformed" },
  ] satisfies readonly BffSessionEvaluation[])(
    "maps unavailable or malformed state to unknown route state",
    (evaluation) => {
      expect(toRouteSession(evaluation)).toEqual({ status: "unknown" });
    },
  );
});
