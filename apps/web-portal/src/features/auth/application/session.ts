import "server-only";

import { headers } from "next/headers";

import type { BffAuthResult } from "@/features/auth/application/bff-auth-service";
import {
  WEB_BFF_SESSION_POLICY_VERSION,
  type SessionSnapshot,
} from "@/features/auth/domain/route-access";
import { readOpaqueSessionCookie } from "@/features/auth/domain/request-security";
import { getServerBffBoundary } from "@/features/auth/infrastructure/server-boundary";

export async function readServerSession(): Promise<BffAuthResult> {
  const boundary = getServerBffBoundary();
  if (boundary.cookieProfile === null) {
    return {
      state: {
        policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
        status: "unavailable",
        errorCode: "SESSION_UNAVAILABLE",
      },
      cookie: { kind: "none" },
      session: null,
    };
  }
  const requestHeaders = await headers();
  const cookieValue = readOpaqueSessionCookie(
    requestHeaders.get("cookie"),
    boundary.cookieProfile.name,
  );
  return boundary.service.read(cookieValue);
}

export async function readSessionSnapshot(): Promise<SessionSnapshot | null> {
  const result = await readServerSession();
  if (result.session) {
    return result.session;
  }
  return result.state.status === "unauthenticated" ||
    result.state.status === "expired" ||
    result.state.status === "revoked" ||
    result.state.status === "mfa_required" ||
    result.state.status === "mfa_failed"
    ? { status: "unauthenticated" }
    : { status: "unknown" };
}
