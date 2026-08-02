import {
  evaluateAuthenticatedSessionSnapshot,
  WEB_BFF_SESSION_POLICY_VERSION,
  type AuthenticatedSessionSnapshot,
  type SessionSnapshot,
} from "./route-access";

export const BFF_SESSION_STATES = [
  "unauthenticated",
  "mfa_required",
  "mfa_failed",
  "authenticated",
  "expired",
  "revoked",
  "unavailable",
  "malformed",
] as const;

export type BffSessionState = (typeof BFF_SESSION_STATES)[number];

export type BffSessionEvaluation =
  | {
      readonly kind: "authenticated";
      readonly session: AuthenticatedSessionSnapshot;
    }
  | {
      readonly kind: "mfa_challenge";
      readonly state: "mfa_required" | "mfa_failed";
    }
  | {
      readonly kind: "login_required";
      readonly state: "unauthenticated" | "expired" | "revoked";
    }
  | { readonly kind: "unavailable" }
  | { readonly kind: "malformed" };

export function evaluateBffSessionSnapshot(
  input: unknown,
  now: Date,
): BffSessionEvaluation {
  if (
    !isRecord(input) ||
    input.policyVersion !== WEB_BFF_SESSION_POLICY_VERSION
  ) {
    return { kind: "malformed" };
  }

  if (input.status === "authenticated") {
    const validation = evaluateAuthenticatedSessionSnapshot(input, now);
    if (validation.kind === "active") {
      return { kind: "authenticated", session: validation.session };
    }
    if (validation.kind === "expired") {
      return { kind: "login_required", state: "expired" };
    }
    return { kind: "malformed" };
  }

  if (!hasExactStateShape(input) || !isBffSessionState(input.status)) {
    return { kind: "malformed" };
  }

  switch (input.status) {
    case "unauthenticated":
    case "expired":
    case "revoked":
      return { kind: "login_required", state: input.status };
    case "mfa_required":
    case "mfa_failed":
      return { kind: "mfa_challenge", state: input.status };
    case "unavailable":
      return { kind: "unavailable" };
    case "malformed":
      return { kind: "malformed" };
    case "authenticated":
      return { kind: "malformed" };
  }
}

export function toRouteSession(
  evaluation: BffSessionEvaluation,
): SessionSnapshot {
  switch (evaluation.kind) {
    case "authenticated":
      return evaluation.session;
    case "login_required":
    case "mfa_challenge":
      return { status: "unauthenticated" };
    case "unavailable":
    case "malformed":
      return { status: "unknown" };
  }
}

function isBffSessionState(value: unknown): value is BffSessionState {
  return (
    typeof value === "string" &&
    (BFF_SESSION_STATES as readonly string[]).includes(value)
  );
}

function hasExactStateShape(value: Record<string, unknown>): boolean {
  const keys = Object.keys(value).sort();
  return (
    keys.length === 2 && keys[0] === "policyVersion" && keys[1] === "status"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
