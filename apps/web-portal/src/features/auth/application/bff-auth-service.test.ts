import { randomBytes } from "node:crypto";

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
} from "@/features/auth/domain/route-access";
import {
  createBffAuthService,
  IDENTITY_SESSION_SNAPSHOT_VERSION,
  IdentityGatewayError,
  type IdentityGateway,
  type IdentitySessionSnapshot,
  type IdentityTokenPair,
  type ServerSessionRecord,
  type ServerSessionStore,
  type SessionMutation,
} from "./bff-auth-service";

const NOW = new Date("2026-08-02T05:00:00.000Z");

class SyntheticSessionStore implements ServerSessionStore {
  private readonly records = new Map<string, ServerSessionRecord>();

  async create(record: ServerSessionRecord): Promise<string> {
    const key = secretValue();
    this.records.set(key, record);
    return key;
  }

  async transact<TResult>(
    cookieValue: string,
    operation: (
      record: ServerSessionRecord,
    ) => Promise<SessionMutation<TResult>>,
  ): Promise<Readonly<{ result: TResult; rotatedCookie?: string }> | null> {
    const record = this.records.get(cookieValue);
    if (!record) return null;
    const mutation = await operation(record);
    if (mutation.action === "replace") {
      this.records.set(cookieValue, mutation.record);
    } else if (mutation.action === "delete") {
      this.records.delete(cookieValue);
    } else if (mutation.action === "rotate") {
      this.records.delete(cookieValue);
      const rotatedCookie = await this.create(mutation.record);
      return { result: mutation.result, rotatedCookie };
    }
    return { result: mutation.result };
  }
}

function tokenPair(): IdentityTokenPair {
  return { accessToken: secretValue(), refreshToken: secretValue() };
}

function identitySnapshot(
  overrides: Partial<IdentitySessionSnapshot> = {},
): IdentitySessionSnapshot {
  return {
    policyVersion: IDENTITY_SESSION_SNAPSHOT_VERSION,
    status: "authenticated",
    sessionId: "10000000-0000-4000-8000-000000000001",
    actorId: "10000000-0000-4000-8000-000000000002",
    tenantId: "10000000-0000-4000-8000-000000000003",
    schoolId: "10000000-0000-4000-8000-000000000004",
    mfaState: "verified",
    issuedAt: "2026-08-02T04:00:00.000Z",
    absoluteExpiresAt: "2026-08-02T09:00:00.000Z",
    inactivityExpiresAt: "2026-08-02T06:00:00.000Z",
    ...overrides,
  };
}

function createIdentity(): IdentityGateway {
  const pair = tokenPair();
  return {
    login: vi.fn().mockResolvedValue(pair),
    refresh: vi.fn().mockResolvedValue(tokenPair()),
    sessionSnapshot: vi.fn().mockResolvedValue(identitySnapshot()),
    logout: vi.fn().mockResolvedValue(undefined),
    logoutAll: vi.fn().mockResolvedValue(undefined),
  };
}

function createSubject(identity = createIdentity()) {
  return {
    identity,
    service: createBffAuthService({
      store: new SyntheticSessionStore(),
      identity,
      authorization: {
        read: vi.fn().mockResolvedValue({
          policyVersion: AUTHORIZATION_POLICY_VERSION,
          permissions: ["attendance.view_metadata"],
        }),
      },
      warning: {
        read: vi.fn().mockResolvedValue("2026-08-02T05:30:00.000Z"),
      },
    }),
  };
}

function credentials(): Record<string, string> {
  return {
    tenantId: "10000000-0000-4000-8000-000000000003",
    identifier: `synthetic-${randomBytes(8).toString("hex")}`,
    password: secretValue(),
  };
}

function secretValue(): string {
  return randomBytes(32).toString("base64url");
}

describe("BFF authentication service", () => {
  it("keeps the challenge usable across tabs and rotates it on login", async () => {
    const { service, identity } = createSubject();
    const first = await service.prepare(null, NOW);
    const cookieValue = cookieFrom(first);
    const otherTab = await service.prepare(cookieValue, NOW);
    expect(otherTab.state.csrfToken).toBe(first.state.csrfToken);
    const loggedIn = await service.login({
      cookieValue,
      csrfToken: first.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    expect(loggedIn.state.status).toBe("authenticated");
    const rotatedCookie = cookieFrom(loggedIn);
    const prepared = await service.prepare(rotatedCookie, NOW);
    expect(prepared.state.csrfToken).not.toBe(first.state.csrfToken);
    const stale = await service.logout({
      cookieValue: rotatedCookie,
      csrfToken: first.state.csrfToken,
      originAccepted: true,
      allDevices: true,
    });
    expect(stale.state.errorCode).toBe("REQUEST_REJECTED");
    expect(identity.logoutAll).not.toHaveBeenCalled();
    await service.prepare(rotatedCookie, NOW);
    const ended = await service.logout({
      cookieValue: rotatedCookie,
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      allDevices: true,
    });
    expect(ended.state.status).toBe("unauthenticated");
    expect(identity.logoutAll).toHaveBeenCalledOnce();
  });

  it("permits correct-password retry without inventing an MFA requirement", async () => {
    const { service, identity } = createSubject();
    vi.mocked(identity.login).mockRejectedValueOnce(
      new IdentityGatewayError(401, "AUTH_CREDENTIAL_INVALID"),
    );
    const prepared = await service.prepare(null, NOW);
    const cookieValue = cookieFrom(prepared);
    const wrong = await service.login({
      cookieValue,
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    expect(wrong.state).toMatchObject({
      status: "unauthenticated",
      errorCode: "AUTH_FAILED",
    });
    const retry = await service.prepare(cookieValue, NOW);
    const correct = await service.login({
      cookieValue,
      csrfToken: retry.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    expect(correct.state.status).toBe("authenticated");
    expect(vi.mocked(identity.login).mock.calls[1][0]).not.toHaveProperty(
      "mfaCode",
    );
  });

  it("keeps the challenge across refresh and rejects tokens from another session", async () => {
    const { service, identity } = createSubject();
    const first = await service.prepare(null, NOW);
    const second = await service.prepare(null, NOW);
    const crossed = await service.login({
      cookieValue: cookieFrom(first),
      csrfToken: second.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    expect(crossed.state.errorCode).toBe("REQUEST_REJECTED");
    expect(identity.login).not.toHaveBeenCalled();
    const authenticated = await service.login({
      cookieValue: cookieFrom(first),
      csrfToken: first.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    const cookieValue = cookieFrom(authenticated);
    const challenge = await service.prepare(cookieValue, NOW);
    vi.mocked(identity.sessionSnapshot).mockRejectedValueOnce(
      new IdentityGatewayError(401, "AUTHENTICATION_REQUIRED"),
    );
    const refreshed = await service.prepare(cookieValue, NOW);
    expect(identity.refresh).toHaveBeenCalledOnce();
    expect(refreshed.state.csrfToken).toBe(challenge.state.csrfToken);
    expect(refreshed.state.status).toBe("authenticated");
  });

  it("does not report logout-all completion from a preauth retry after upstream failure", async () => {
    const { service, identity } = createSubject();
    const prepared = await service.prepare(null, NOW);
    const loggedIn = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    const active = await service.prepare(cookieFrom(loggedIn), NOW);
    vi.mocked(identity.logoutAll).mockRejectedValueOnce(
      new IdentityGatewayError(503, "AUTH_DEPENDENCY_UNAVAILABLE"),
    );
    const failed = await service.logout({
      cookieValue: cookieFrom(loggedIn),
      csrfToken: active.state.csrfToken,
      originAccepted: true,
      allDevices: true,
    });
    expect(failed.cookie.kind).toBe("clear");
    expect(failed.state.errorCode).toBe("SESSION_UNAVAILABLE");
    const preauth = await service.prepare(null, NOW);
    const retry = await service.logout({
      cookieValue: cookieFrom(preauth),
      csrfToken: preauth.state.csrfToken,
      originAccepted: true,
      allDevices: true,
    });
    expect(retry.state.errorCode).toBe("REQUEST_REJECTED");
    expect(identity.logoutAll).toHaveBeenCalledOnce();
  });
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("creates an opaque pre-auth session and session-bound CSRF challenge", async () => {
    const { service } = createSubject();
    const prepared = await service.prepare(null, NOW);

    expect(prepared.state).toMatchObject({
      policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
      status: "unauthenticated",
      errorCode: "AUTH_REQUIRED",
    });
    expect(prepared.state.csrfToken).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(prepared.cookie.kind).toBe("set");
  });

  it("rejects missing origin or CSRF before contacting Identity", async () => {
    const { service, identity } = createSubject();
    const prepared = await service.prepare(null, NOW);
    const cookieValue = cookieFrom(prepared);

    const result = await service.login({
      cookieValue,
      csrfToken: prepared.state.csrfToken,
      originAccepted: false,
      credentials: credentials(),
      now: NOW,
    });

    expect(result.state.errorCode).toBe("REQUEST_REJECTED");
    expect(identity.login).not.toHaveBeenCalled();

    const missingCsrf = await service.login({
      cookieValue,
      csrfToken: null,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    expect(missingCsrf.state.errorCode).toBe("REQUEST_REJECTED");
    expect(identity.login).not.toHaveBeenCalled();
  });

  it("rejects client-authored authority fields before contacting Identity", async () => {
    const { service, identity } = createSubject();
    const prepared = await service.prepare(null, NOW);

    const result = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: {
        ...credentials(),
        permissions: ["audit.export"],
      },
      now: NOW,
    });

    expect(result.state.errorCode).toBe("AUTH_FAILED");
    expect(identity.login).not.toHaveBeenCalled();
  });

  it.each([
    ["AUTH_MFA_REQUIRED", "mfa_required", "MFA_REQUIRED"],
    ["AUTH_MFA_VERIFICATION_FAILED", "mfa_failed", "AUTH_FAILED"],
    ["AUTH_CREDENTIAL_INVALID", "unauthenticated", "AUTH_FAILED"],
  ] as const)(
    "maps %s to a non-enumerating public state",
    async (upstreamCode, status, errorCode) => {
      const identity = createIdentity();
      vi.mocked(identity.login).mockRejectedValueOnce(
        new IdentityGatewayError(401, upstreamCode),
      );
      const { service } = createSubject(identity);
      const prepared = await service.prepare(null, NOW);

      const result = await service.login({
        cookieValue: cookieFrom(prepared),
        csrfToken: prepared.state.csrfToken,
        originAccepted: true,
        credentials: credentials(),
        now: NOW,
      });

      expect(result.state).toMatchObject({ status, errorCode });
      expect(JSON.stringify(result.state)).not.toContain(upstreamCode);
    },
  );

  it("rotates the opaque cookie only after an exact authoritative snapshot", async () => {
    const { service } = createSubject();
    const prepared = await service.prepare(null, NOW);
    const originalCookie = cookieFrom(prepared);

    const result = await service.login({
      cookieValue: originalCookie,
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });

    expect(result.state).toMatchObject({
      status: "authenticated",
      errorCode: "AUTHENTICATED",
      sessionWarning: false,
    });
    expect(result.session?.authorization).toEqual({
      policyVersion: AUTHORIZATION_POLICY_VERSION,
      permissions: ["attendance.view_metadata"],
    });
    expect(cookieFrom(result)).not.toBe(originalCookie);
    expect(JSON.stringify(result.state)).not.toContain("accessToken");
    expect(JSON.stringify(result.state)).not.toContain("refreshToken");
  });

  it("fails closed and revokes the fresh Identity session on malformed scope", async () => {
    const identity = createIdentity();
    vi.mocked(identity.sessionSnapshot).mockResolvedValueOnce(
      identitySnapshot({ schoolId: null }),
    );
    const { service } = createSubject(identity);
    const prepared = await service.prepare(null, NOW);

    const result = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });

    expect(result.state.errorCode).toBe("SESSION_INVALID");
    expect(result.cookie.kind).toBe("clear");
    expect(identity.logout).toHaveBeenCalledOnce();
  });

  it("refreshes under the server transaction and persists only the rotated pair", async () => {
    const identity = createIdentity();
    vi.mocked(identity.sessionSnapshot)
      .mockRejectedValueOnce(
        new IdentityGatewayError(401, "AUTHENTICATION_REQUIRED"),
      )
      .mockResolvedValueOnce(identitySnapshot());
    const { service } = createSubject(identity);
    const prepared = await service.prepare(null, NOW);
    const loggedIn = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });

    expect(loggedIn.state.status).toBe("authenticated");
    expect(identity.refresh).toHaveBeenCalledOnce();
    expect(identity.sessionSnapshot).toHaveBeenCalledTimes(2);
  });

  it("clears local access when refresh replay is reported", async () => {
    const identity = createIdentity();
    const { service } = createSubject(identity);
    const prepared = await service.prepare(null, NOW);
    const loggedIn = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    vi.mocked(identity.sessionSnapshot).mockRejectedValueOnce(
      new IdentityGatewayError(401, "AUTHENTICATION_REQUIRED"),
    );
    vi.mocked(identity.refresh).mockRejectedValueOnce(
      new IdentityGatewayError(401, "AUTH_REFRESH_REUSE_DETECTED"),
    );

    const result = await service.read(cookieFrom(loggedIn), NOW);

    expect(result.state.status).toBe("revoked");
    expect(result.cookie.kind).toBe("clear");
    expect(result.session).toBeNull();
  });

  it("persists a rotated pair when the post-refresh snapshot is unavailable", async () => {
    const identity = createIdentity();
    const { service } = createSubject(identity);
    const prepared = await service.prepare(null, NOW);
    const loggedIn = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    const rotated = tokenPair();
    vi.mocked(identity.refresh).mockResolvedValueOnce(rotated);
    vi.mocked(identity.sessionSnapshot)
      .mockRejectedValueOnce(
        new IdentityGatewayError(401, "AUTHENTICATION_REQUIRED"),
      )
      .mockRejectedValueOnce(
        new IdentityGatewayError(503, "AUTH_DEPENDENCY_UNAVAILABLE"),
      )
      .mockResolvedValueOnce(identitySnapshot());

    const unavailable = await service.read(cookieFrom(loggedIn), NOW);
    expect(unavailable.state.status).toBe("unavailable");
    const recovered = await service.read(cookieFrom(loggedIn), NOW);

    expect(recovered.state.status).toBe("authenticated");
    expect(identity.sessionSnapshot).toHaveBeenLastCalledWith(
      rotated.accessToken,
    );
  });

  it("shows the authoritative warning without calling refresh or extending expiry", async () => {
    const identity = createIdentity();
    const { service } = createSubject(identity);
    const prepared = await service.prepare(null, NOW);
    const loggedIn = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: new Date("2026-08-02T05:45:00.000Z"),
    });

    expect(loggedIn.state.sessionWarning).toBe(true);
    expect(identity.refresh).not.toHaveBeenCalled();
    expect(loggedIn.session?.inactivityExpiresAt).toBe(
      "2026-08-02T06:00:00.000Z",
    );
  });

  it("clears local access but does not claim revocation when logout is unavailable", async () => {
    const identity = createIdentity();
    vi.mocked(identity.logout).mockRejectedValueOnce(
      new IdentityGatewayError(503, "AUTH_DEPENDENCY_UNAVAILABLE"),
    );
    const { service } = createSubject(identity);
    const prepared = await service.prepare(null, NOW);
    const loggedIn = await service.login({
      cookieValue: cookieFrom(prepared),
      csrfToken: prepared.state.csrfToken,
      originAccepted: true,
      credentials: credentials(),
      now: NOW,
    });
    const challenge = await service.prepare(cookieFrom(loggedIn), NOW);

    const result = await service.logout({
      cookieValue: cookieFrom(loggedIn),
      csrfToken: challenge.state.csrfToken,
      originAccepted: true,
      allDevices: false,
    });

    expect(result.state.errorCode).toBe("SESSION_UNAVAILABLE");
    expect(result.cookie.kind).toBe("clear");
  });
});

function cookieFrom(result: {
  cookie: { kind: string; value?: string };
}): string {
  if (result.cookie.kind !== "set" || !result.cookie.value) {
    throw new Error("Synthetic session cookie was not issued.");
  }
  return result.cookie.value;
}
