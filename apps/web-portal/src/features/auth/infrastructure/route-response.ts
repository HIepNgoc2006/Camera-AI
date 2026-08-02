import "server-only";

import type {
  BffAuthResult,
  PublicAuthState,
} from "@/features/auth/application/bff-auth-service";
import {
  serializeClearedSessionCookie,
  serializeSessionCookie,
  type SessionCookieProfile,
} from "@/features/auth/domain/request-security";

const NO_STORE_HEADERS = {
  "Cache-Control": "private, no-store",
  "Content-Type": "application/json",
  Pragma: "no-cache",
} as const;

export function authJsonResponse(
  result: BffAuthResult,
  cookieProfile: SessionCookieProfile | null,
  redirectTo?: "/app" | "/login",
): Response {
  let state: PublicAuthState = result.state;
  let status = responseStatus(state.errorCode);
  const headers = new Headers(NO_STORE_HEADERS);

  if (result.cookie.kind !== "none") {
    if (cookieProfile === null) {
      state = {
        policyVersion: result.state.policyVersion,
        status: "unavailable",
        errorCode: "SESSION_UNAVAILABLE",
      };
      status = 503;
    } else {
      try {
        headers.set(
          "Set-Cookie",
          result.cookie.kind === "set"
            ? serializeSessionCookie(cookieProfile, result.cookie.value)
            : serializeClearedSessionCookie(cookieProfile),
        );
      } catch {
        state = {
          policyVersion: result.state.policyVersion,
          status: "unavailable",
          errorCode: "SESSION_UNAVAILABLE",
        };
        status = 503;
      }
    }
  }

  return new Response(
    JSON.stringify({
      ...state,
      ...(redirectTo && status < 400 ? { redirectTo } : {}),
    }),
    { status, headers },
  );
}

export async function readBoundedJson(request: Request): Promise<unknown> {
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (
    !contentType.startsWith("application/json") ||
    !Number.isFinite(contentLength) ||
    contentLength < 0 ||
    contentLength > 8192
  ) {
    return null;
  }
  try {
    const text = await readBodyAtMost(request, 8192);
    return text === null ? null : (JSON.parse(text) as unknown);
  } catch {
    return null;
  }
}

async function readBodyAtMost(
  request: Request,
  maximumBytes: number,
): Promise<string | null> {
  if (!request.body) return null;
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maximumBytes) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const combined = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    combined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(combined);
}

function responseStatus(errorCode: PublicAuthState["errorCode"]): number {
  if (errorCode === "REQUEST_REJECTED") {
    return 403;
  }
  if (errorCode === "SESSION_UNAVAILABLE") {
    return 503;
  }
  if (errorCode === "SESSION_INVALID") {
    return 401;
  }
  return 200;
}
