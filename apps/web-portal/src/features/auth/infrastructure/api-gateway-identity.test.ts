import { randomBytes } from "node:crypto";

import { describe, expect, it, vi } from "vitest";

import { IdentityGatewayError } from "@/features/auth/application/bff-auth-service";
import {
  ApiGatewayResponseError,
  type ApiGatewayClient,
} from "@/shared/api/api-gateway-client";
import { createApiGatewayIdentity } from "./api-gateway-identity";

function clientReturning(value: unknown): ApiGatewayClient {
  return {
    request: vi.fn().mockResolvedValue(value) as ApiGatewayClient["request"],
  };
}

function secretValue(): string {
  return randomBytes(32).toString("base64url");
}

function tokenResponse(): Record<string, unknown> {
  return {
    access_token: secretValue(),
    refresh_token: secretValue(),
    token_type: "Bearer",
    expires_in: 300,
    session_id: "20000000-0000-4000-8000-000000000001",
    mfa_verified: true,
    request_id: "synthetic-request",
  };
}

function snapshotResponse(): Record<string, unknown> {
  return {
    policyVersion: "identity_session_snapshot_v1",
    status: "authenticated",
    sessionId: "20000000-0000-4000-8000-000000000001",
    actorId: "20000000-0000-4000-8000-000000000002",
    tenantId: "20000000-0000-4000-8000-000000000003",
    schoolId: "20000000-0000-4000-8000-000000000004",
    mfaState: "verified",
    issuedAt: "2026-08-02T04:00:00.000Z",
    absoluteExpiresAt: "2026-08-02T09:00:00.000Z",
    inactivityExpiresAt: "2026-08-02T06:00:00.000Z",
    request_id: "synthetic-request",
  };
}

describe("API Gateway Identity adapter", () => {
  it("maps an exact token response without exposing other fields", async () => {
    const response = tokenResponse();
    const identity = createApiGatewayIdentity(clientReturning(response));

    await expect(
      identity.login({
        tenantId: "20000000-0000-4000-8000-000000000003",
        identifier: "synthetic-account",
        password: secretValue(),
      }),
    ).resolves.toEqual({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    });
  });

  it("accepts only the exact Identity snapshot version and field set", async () => {
    const response = snapshotResponse();
    const identity = createApiGatewayIdentity(clientReturning(response));

    await expect(
      identity.sessionSnapshot(secretValue()),
    ).resolves.toMatchObject({
      policyVersion: "identity_session_snapshot_v1",
      status: "authenticated",
      actorId: response.actorId,
      tenantId: response.tenantId,
    });

    const augmented = createApiGatewayIdentity(
      clientReturning({ ...response, clientPermission: "forged" }),
    );
    await expect(augmented.sessionSnapshot(secretValue())).rejects.toEqual(
      new IdentityGatewayError(502, "IDENTITY_RESPONSE_MALFORMED"),
    );
  });

  it("preserves only a stable upstream error code", async () => {
    const client: ApiGatewayClient = {
      request: vi
        .fn()
        .mockRejectedValue(
          new ApiGatewayResponseError(401, "AUTH_MFA_REQUIRED"),
        ) as ApiGatewayClient["request"],
    };
    const identity = createApiGatewayIdentity(client);

    await expect(
      identity.login({
        tenantId: "20000000-0000-4000-8000-000000000003",
        identifier: "synthetic-account",
        password: secretValue(),
      }),
    ).rejects.toEqual(new IdentityGatewayError(401, "AUTH_MFA_REQUIRED"));
  });

  it("rejects a malformed operation response without surfacing its content", async () => {
    const identity = createApiGatewayIdentity(
      clientReturning({
        operation: "unexpected",
        request_id: "synthetic-request",
      }),
    );

    await expect(identity.logout(secretValue())).rejects.toEqual(
      new IdentityGatewayError(502, "IDENTITY_RESPONSE_MALFORMED"),
    );
  });
});
