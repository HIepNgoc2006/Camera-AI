import {
  IDENTITY_SESSION_SNAPSHOT_VERSION,
  IdentityGatewayError,
  type IdentityGateway,
  type IdentitySessionSnapshot,
  type IdentityTokenPair,
} from "@/features/auth/application/bff-auth-service";
import {
  ApiGatewayResponseError,
  type ApiGatewayClient,
} from "@/shared/api/api-gateway-client";

const LOGIN_PATH = "/api/v1/auth/login" as const;
const REFRESH_PATH = "/api/v1/auth/refresh" as const;
const SNAPSHOT_PATH = "/api/v1/auth/session/snapshot" as const;
const LOGOUT_PATH = "/api/v1/auth/logout" as const;
const LOGOUT_ALL_PATH = "/api/v1/auth/logout-all" as const;

export function createApiGatewayIdentity(
  client: ApiGatewayClient,
): IdentityGateway {
  return {
    async login(input) {
      return requestTokenPair(client, LOGIN_PATH, {
        tenant_id: input.tenantId,
        identifier: input.identifier,
        password: input.password,
        ...(input.mfaCode ? { mfa_code: input.mfaCode } : {}),
      });
    },
    async refresh(refreshToken) {
      return requestTokenPair(client, REFRESH_PATH, {
        refresh_token: refreshToken,
      });
    },
    async sessionSnapshot(accessToken) {
      try {
        const payload = await client.request<unknown>(SNAPSHOT_PATH, {
          method: "POST",
          headers: authorizationHeaders(accessToken),
        });
        const snapshot = parseIdentitySnapshot(payload);
        if (snapshot === null) {
          throw new IdentityGatewayError(502, "IDENTITY_RESPONSE_MALFORMED");
        }
        return snapshot;
      } catch (error) {
        throw mapGatewayError(error);
      }
    },
    async logout(accessToken) {
      await requestOperation(client, LOGOUT_PATH, accessToken, "logout");
    },
    async logoutAll(accessToken) {
      await requestOperation(
        client,
        LOGOUT_ALL_PATH,
        accessToken,
        "logout_all",
      );
    },
  };
}

async function requestTokenPair(
  client: ApiGatewayClient,
  path: typeof LOGIN_PATH | typeof REFRESH_PATH,
  body: Readonly<Record<string, string>>,
): Promise<IdentityTokenPair> {
  try {
    const payload = await client.request<unknown>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const pair = parseTokenPair(payload);
    if (pair === null) {
      throw new IdentityGatewayError(502, "IDENTITY_RESPONSE_MALFORMED");
    }
    return pair;
  } catch (error) {
    throw mapGatewayError(error);
  }
}

async function requestOperation(
  client: ApiGatewayClient,
  path: typeof LOGOUT_PATH | typeof LOGOUT_ALL_PATH,
  accessToken: string,
  operation: "logout" | "logout_all",
): Promise<void> {
  try {
    const payload = await client.request<unknown>(path, {
      method: "POST",
      headers: authorizationHeaders(accessToken),
    });
    if (
      !isRecord(payload) ||
      payload.operation !== operation ||
      typeof payload.request_id !== "string"
    ) {
      throw new IdentityGatewayError(502, "IDENTITY_RESPONSE_MALFORMED");
    }
  } catch (error) {
    throw mapGatewayError(error);
  }
}

function authorizationHeaders(accessToken: string): HeadersInit {
  if (!isServerToken(accessToken)) {
    throw new IdentityGatewayError(401, "AUTHENTICATION_REQUIRED");
  }
  return { Authorization: `Bearer ${accessToken}` };
}

function parseTokenPair(value: unknown): IdentityTokenPair | null {
  if (!isRecord(value) || !hasExactKeys(value, TOKEN_RESPONSE_KEYS)) {
    return null;
  }
  if (
    !isServerToken(value.access_token) ||
    !isServerToken(value.refresh_token) ||
    value.token_type !== "Bearer" ||
    !Number.isInteger(value.expires_in) ||
    (value.expires_in as number) <= 0 ||
    !isUuid(value.session_id) ||
    typeof value.mfa_verified !== "boolean" ||
    typeof value.request_id !== "string" ||
    value.request_id.length < 1 ||
    value.request_id.length > 128
  ) {
    return null;
  }
  return {
    accessToken: value.access_token,
    refreshToken: value.refresh_token,
  };
}

function parseIdentitySnapshot(value: unknown): IdentitySessionSnapshot | null {
  if (!isRecord(value) || !hasExactKeys(value, SNAPSHOT_RESPONSE_KEYS)) {
    return null;
  }
  if (
    value.policyVersion !== IDENTITY_SESSION_SNAPSHOT_VERSION ||
    value.status !== "authenticated" ||
    !isUuid(value.sessionId) ||
    !isUuid(value.actorId) ||
    !isUuid(value.tenantId) ||
    !(value.schoolId === null || isUuid(value.schoolId)) ||
    !["verified", "not_required"].includes(String(value.mfaState)) ||
    !isCanonicalUtc(value.issuedAt) ||
    !isCanonicalUtc(value.absoluteExpiresAt) ||
    !isCanonicalUtc(value.inactivityExpiresAt) ||
    typeof value.request_id !== "string" ||
    value.request_id.length < 1 ||
    value.request_id.length > 128
  ) {
    return null;
  }
  return {
    policyVersion: IDENTITY_SESSION_SNAPSHOT_VERSION,
    status: "authenticated",
    sessionId: value.sessionId,
    actorId: value.actorId,
    tenantId: value.tenantId,
    schoolId: value.schoolId,
    mfaState: value.mfaState as "verified" | "not_required",
    issuedAt: value.issuedAt,
    absoluteExpiresAt: value.absoluteExpiresAt,
    inactivityExpiresAt: value.inactivityExpiresAt,
  };
}

function mapGatewayError(error: unknown): IdentityGatewayError {
  if (error instanceof IdentityGatewayError) {
    return error;
  }
  if (error instanceof ApiGatewayResponseError) {
    return new IdentityGatewayError(error.status, error.upstreamErrorCode);
  }
  return new IdentityGatewayError(503, "AUTH_DEPENDENCY_UNAVAILABLE");
}

function isServerToken(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length >= 32 &&
    value.length <= 4096 &&
    !/[\s,]/.test(value)
  );
}

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  );
}

function isCanonicalUtc(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const TOKEN_RESPONSE_KEYS = [
  "access_token",
  "expires_in",
  "mfa_verified",
  "refresh_token",
  "request_id",
  "session_id",
  "token_type",
] as const;

const SNAPSHOT_RESPONSE_KEYS = [
  "absoluteExpiresAt",
  "actorId",
  "inactivityExpiresAt",
  "issuedAt",
  "mfaState",
  "policyVersion",
  "request_id",
  "schoolId",
  "sessionId",
  "status",
  "tenantId",
] as const;
