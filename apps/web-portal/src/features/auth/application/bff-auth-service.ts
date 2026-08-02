import { createHash, randomBytes } from "node:crypto";

import {
  evaluateBffSessionSnapshot,
  type BffSessionEvaluation,
  type BffSessionState,
} from "@/features/auth/domain/bff-session";
import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type AuthenticatedSessionSnapshot,
} from "@/features/auth/domain/route-access";
import { constantTimeCsrfMatch } from "@/features/auth/domain/request-security";

export const IDENTITY_SESSION_SNAPSHOT_VERSION =
  "identity_session_snapshot_v1" as const;

export type IdentityTokenPair = Readonly<{
  accessToken: string;
  refreshToken: string;
}>;

export type IdentitySessionSnapshot = Readonly<{
  policyVersion: typeof IDENTITY_SESSION_SNAPSHOT_VERSION;
  status: "authenticated";
  sessionId: string;
  actorId: string;
  tenantId: string;
  schoolId: string | null;
  mfaState: "verified" | "not_required";
  issuedAt: string;
  absoluteExpiresAt: string;
  inactivityExpiresAt: string;
}>;

export type AuthorizationSnapshot = Readonly<{
  policyVersion: typeof AUTHORIZATION_POLICY_VERSION;
  permissions: readonly string[];
}>;

export class IdentityGatewayError extends Error {
  constructor(
    readonly status: number,
    readonly errorCode: string | null,
  ) {
    super("Identity request failed.");
    this.name = "IdentityGatewayError";
  }
}

export interface IdentityGateway {
  login(input: {
    tenantId: string;
    identifier: string;
    password: string;
    mfaCode?: string;
  }): Promise<IdentityTokenPair>;
  refresh(refreshToken: string): Promise<IdentityTokenPair>;
  sessionSnapshot(accessToken: string): Promise<IdentitySessionSnapshot>;
  logout(accessToken: string): Promise<void>;
  logoutAll(accessToken: string): Promise<void>;
}

export interface AuthorizationSnapshotProvider {
  read(
    accessToken: string,
    identity: IdentitySessionSnapshot,
  ): Promise<AuthorizationSnapshot>;
}

export interface WarningTimestampProvider {
  read(identity: IdentitySessionSnapshot): Promise<string>;
}

type PreAuthSessionRecord = Readonly<{
  status: "unauthenticated" | "mfa_required" | "mfa_failed";
  csrfDigest: Uint8Array;
}>;

type AuthenticatedSessionRecord = Readonly<{
  status: "authenticated";
  csrfDigest: Uint8Array;
  tokens: IdentityTokenPair;
}>;

export type ServerSessionRecord =
  PreAuthSessionRecord | AuthenticatedSessionRecord;

export type SessionMutation<TResult> =
  | Readonly<{ action: "keep"; result: TResult }>
  | Readonly<{
      action: "replace";
      record: ServerSessionRecord;
      result: TResult;
    }>
  | Readonly<{ action: "rotate"; record: ServerSessionRecord; result: TResult }>
  | Readonly<{ action: "delete"; result: TResult }>;

export interface ServerSessionStore {
  create(record: ServerSessionRecord): Promise<string>;
  /**
   * The provider must serialize each cookie's callback and apply its mutation
   * atomically. This prevents concurrent refresh from replaying a just-rotated
   * refresh token.
   */
  transact<TResult>(
    cookieValue: string,
    operation: (
      record: ServerSessionRecord,
    ) => Promise<SessionMutation<TResult>>,
  ): Promise<Readonly<{ result: TResult; rotatedCookie?: string }> | null>;
}

export type PublicAuthState = Readonly<{
  policyVersion: typeof WEB_BFF_SESSION_POLICY_VERSION;
  status: BffSessionState;
  errorCode:
    | "AUTH_REQUIRED"
    | "MFA_REQUIRED"
    | "AUTH_FAILED"
    | "AUTHENTICATED"
    | "SESSION_UNAVAILABLE"
    | "SESSION_INVALID"
    | "REQUEST_REJECTED";
  csrfToken?: string;
  sessionWarning?: boolean;
}>;

export type CookieDirective =
  | Readonly<{ kind: "none" }>
  | Readonly<{ kind: "set"; value: string }>
  | Readonly<{ kind: "clear" }>;

export type BffAuthResult = Readonly<{
  state: PublicAuthState;
  cookie: CookieDirective;
  session: AuthenticatedSessionSnapshot | null;
}>;

export type LoginInput = Readonly<{
  tenantId: string;
  identifier: string;
  password: string;
  mfaCode?: string;
}>;

export interface BffAuthService {
  prepare(cookieValue: string | null, now?: Date): Promise<BffAuthResult>;
  read(cookieValue: string | null, now?: Date): Promise<BffAuthResult>;
  login(input: {
    cookieValue: string | null;
    csrfToken: unknown;
    originAccepted: boolean;
    credentials: unknown;
    now?: Date;
  }): Promise<BffAuthResult>;
  logout(input: {
    cookieValue: string | null;
    csrfToken: unknown;
    originAccepted: boolean;
    allDevices: boolean;
  }): Promise<BffAuthResult>;
}

type Dependencies = Readonly<{
  store: ServerSessionStore;
  identity: IdentityGateway;
  authorization: AuthorizationSnapshotProvider;
  warning: WarningTimestampProvider;
}>;

type ResolvedSession = Readonly<{
  evaluation: BffSessionEvaluation;
  tokens: IdentityTokenPair;
}>;

export function createBffAuthService(
  dependencies: Dependencies,
): BffAuthService {
  return {
    async prepare(cookieValue, now = new Date()) {
      if (cookieValue === null) {
        return createPreAuthSession(dependencies.store);
      }

      const csrfToken = newSecret();
      const transaction = await dependencies.store.transact(
        cookieValue,
        async (record) => {
          const resolved = await resolveRecord(record, dependencies, now);
          if (resolved.evaluation.kind === "authenticated") {
            return {
              action: "replace",
              record: {
                status: "authenticated",
                csrfDigest: digestSecret(csrfToken),
                tokens: resolved.tokens,
              },
              result: resultFromEvaluation(
                resolved.evaluation,
                { kind: "none" },
                csrfToken,
                now,
              ),
            };
          }
          if (
            resolved.evaluation.kind === "login_required" ||
            resolved.evaluation.kind === "mfa_challenge"
          ) {
            return {
              action: "replace",
              record: {
                status:
                  resolved.evaluation.kind === "mfa_challenge"
                    ? resolved.evaluation.state
                    : "unauthenticated",
                csrfDigest: digestSecret(csrfToken),
              },
              result: resultFromEvaluation(
                resolved.evaluation,
                { kind: "none" },
                csrfToken,
                now,
              ),
            };
          }
          return resolvedFailureMutation(record, resolved, now);
        },
      );

      if (transaction === null) {
        return createPreAuthSession(dependencies.store);
      }
      return applyRotatedCookie(transaction);
    },

    async read(cookieValue, now = new Date()) {
      if (cookieValue === null) {
        return simpleResult("unauthenticated", { kind: "none" });
      }
      const transaction = await dependencies.store.transact(
        cookieValue,
        async (record) => {
          const resolved = await resolveRecord(record, dependencies, now);
          const evaluation = resolved.evaluation;
          if (evaluation.kind === "authenticated") {
            return authenticatedResolutionMutation(record, resolved, now);
          }
          return resolvedFailureMutation(record, resolved, now);
        },
      );
      return transaction === null
        ? simpleResult("unauthenticated", { kind: "clear" })
        : applyRotatedCookie(transaction);
    },

    async login({
      cookieValue,
      csrfToken,
      originAccepted,
      credentials,
      now = new Date(),
    }) {
      if (!originAccepted || cookieValue === null) {
        return rejectedResult();
      }
      const parsed = parseLoginInput(credentials);
      const transaction = await dependencies.store.transact(
        cookieValue,
        async (record) => {
          if (!validCsrf(csrfToken, record.csrfDigest)) {
            return { action: "keep", result: rejectedResult() };
          }
          if (record.status === "authenticated") {
            const resolved = await resolveRecord(record, dependencies, now);
            return resolved.evaluation.kind === "authenticated"
              ? authenticatedResolutionMutation(record, resolved, now)
              : resolvedFailureMutation(record, resolved, now);
          }
          if (parsed === null) {
            return failedLoginMutation(record.csrfDigest);
          }

          let tokens: IdentityTokenPair;
          try {
            tokens = await dependencies.identity.login(parsed);
          } catch (error) {
            if (isIdentityError(error, "AUTH_MFA_REQUIRED")) {
              return stateMutation("mfa_required", record.csrfDigest);
            }
            if (
              isIdentityError(error, "AUTH_MFA_VERIFICATION_FAILED") ||
              isIdentityError(error, "AUTH_CREDENTIAL_INVALID")
            ) {
              return failedLoginMutation(record.csrfDigest);
            }
            return {
              action: "keep",
              result: simpleResult("unavailable", { kind: "none" }),
            };
          }

          const resolved = await resolveTokens(tokens, dependencies, now);
          if (resolved.evaluation.kind !== "authenticated") {
            await bestEffortLogout(
              dependencies.identity,
              resolved.tokens.accessToken,
            );
            return {
              action: "delete",
              result: resultFromEvaluation(
                resolved.evaluation,
                { kind: "clear" },
                undefined,
                now,
              ),
            };
          }
          return {
            action: "rotate",
            record: {
              status: "authenticated",
              csrfDigest: digestSecret(newSecret()),
              tokens: resolved.tokens,
            },
            result: resultFromEvaluation(
              resolved.evaluation,
              { kind: "none" },
              undefined,
              now,
            ),
          };
        },
      );
      if (transaction === null) {
        return rejectedResult({ kind: "clear" });
      }
      return applyRotatedCookie(transaction);
    },

    async logout({ cookieValue, csrfToken, originAccepted, allDevices }) {
      if (!originAccepted || cookieValue === null) {
        return rejectedResult();
      }
      const transaction = await dependencies.store.transact(
        cookieValue,
        async (record) => {
          if (!validCsrf(csrfToken, record.csrfDigest)) {
            return { action: "keep", result: rejectedResult() };
          }
          if (record.status !== "authenticated") {
            return {
              action: "delete",
              result: simpleResult("unauthenticated", { kind: "clear" }),
            };
          }
          try {
            if (allDevices) {
              await dependencies.identity.logoutAll(record.tokens.accessToken);
            } else {
              await dependencies.identity.logout(record.tokens.accessToken);
            }
            return {
              action: "delete",
              result: simpleResult("unauthenticated", { kind: "clear" }),
            };
          } catch {
            return {
              action: "delete",
              result: simpleResult("unavailable", { kind: "clear" }),
            };
          }
        },
      );
      return transaction === null
        ? simpleResult("unauthenticated", { kind: "clear" })
        : applyRotatedCookie(transaction);
    },
  };
}

async function createPreAuthSession(
  store: ServerSessionStore,
): Promise<BffAuthResult> {
  const csrfToken = newSecret();
  try {
    const cookieValue = await store.create({
      status: "unauthenticated",
      csrfDigest: digestSecret(csrfToken),
    });
    return simpleResult(
      "unauthenticated",
      { kind: "set", value: cookieValue },
      csrfToken,
    );
  } catch {
    return simpleResult("unavailable", { kind: "none" });
  }
}

async function resolveRecord(
  record: ServerSessionRecord,
  dependencies: Dependencies,
  now: Date,
): Promise<ResolvedSession> {
  if (record.status !== "authenticated") {
    return {
      evaluation: evaluateBffSessionSnapshot(
        {
          policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
          status: record.status,
        },
        now,
      ),
      tokens: { accessToken: "", refreshToken: "" },
    };
  }
  return resolveTokens(record.tokens, dependencies, now);
}

async function resolveTokens(
  initialTokens: IdentityTokenPair,
  dependencies: Dependencies,
  now: Date,
): Promise<ResolvedSession> {
  let tokens = initialTokens;
  let identity: IdentitySessionSnapshot;
  try {
    identity = await dependencies.identity.sessionSnapshot(tokens.accessToken);
  } catch (error) {
    if (!isIdentityError(error, "AUTHENTICATION_REQUIRED")) {
      return {
        evaluation: unavailableOrMalformed(error),
        tokens,
      };
    }
    try {
      tokens = await dependencies.identity.refresh(tokens.refreshToken);
      identity = await dependencies.identity.sessionSnapshot(
        tokens.accessToken,
      );
    } catch (refreshError) {
      const state = isIdentityError(refreshError, "AUTH_REFRESH_REUSE_DETECTED")
        ? "revoked"
        : isUnavailableIdentityError(refreshError)
          ? "unavailable"
          : "expired";
      return {
        evaluation: evaluateBffSessionSnapshot(
          { policyVersion: WEB_BFF_SESSION_POLICY_VERSION, status: state },
          now,
        ),
        tokens,
      };
    }
  }

  try {
    const [authorization, warningStartsAt] = await Promise.all([
      dependencies.authorization.read(tokens.accessToken, identity),
      dependencies.warning.read(identity),
    ]);
    const candidate = {
      policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
      status: "authenticated",
      actorId: identity.actorId,
      tenantId: identity.tenantId,
      schoolId: identity.schoolId,
      mfaState: identity.mfaState,
      issuedAt: identity.issuedAt,
      absoluteExpiresAt: identity.absoluteExpiresAt,
      inactivityExpiresAt: identity.inactivityExpiresAt,
      warningStartsAt,
      authorization,
    };
    return {
      evaluation: evaluateBffSessionSnapshot(candidate, now),
      tokens,
    };
  } catch {
    return {
      evaluation: evaluateBffSessionSnapshot(
        {
          policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
          status: "unavailable",
        },
        now,
      ),
      tokens,
    };
  }
}

function unavailableOrMalformed(error: unknown): BffSessionEvaluation {
  return evaluateBffSessionSnapshot(
    {
      policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
      status: isUnavailableIdentityError(error) ? "unavailable" : "malformed",
    },
    new Date(0),
  );
}

function resultFromEvaluation(
  evaluation: BffSessionEvaluation,
  cookie: CookieDirective,
  csrfToken: string | undefined,
  now: Date,
): BffAuthResult {
  if (evaluation.kind === "authenticated") {
    return {
      state: {
        policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
        status: "authenticated",
        errorCode: "AUTHENTICATED",
        ...(csrfToken ? { csrfToken } : {}),
        sessionWarning:
          now.getTime() >= Date.parse(evaluation.session.warningStartsAt),
      },
      cookie,
      session: evaluation.session,
    };
  }
  if (evaluation.kind === "mfa_challenge") {
    return simpleResult(evaluation.state, cookie, csrfToken);
  }
  if (evaluation.kind === "login_required") {
    return simpleResult(evaluation.state, cookie, csrfToken);
  }
  return simpleResult(evaluation.kind, cookie, csrfToken);
}

function simpleResult(
  status: Exclude<BffSessionState, "authenticated">,
  cookie: CookieDirective,
  csrfToken?: string,
): BffAuthResult {
  const errorCode: PublicAuthState["errorCode"] =
    status === "mfa_required"
      ? "MFA_REQUIRED"
      : status === "mfa_failed"
        ? "AUTH_FAILED"
        : status === "unavailable"
          ? "SESSION_UNAVAILABLE"
          : status === "malformed"
            ? "SESSION_INVALID"
            : "AUTH_REQUIRED";
  return {
    state: {
      policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
      status,
      errorCode,
      ...(csrfToken ? { csrfToken } : {}),
    },
    cookie,
    session: null,
  };
}

function rejectedResult(
  cookie: CookieDirective = { kind: "none" },
): BffAuthResult {
  return {
    state: {
      policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
      status: "unauthenticated",
      errorCode: "REQUEST_REJECTED",
    },
    cookie,
    session: null,
  };
}

function stateMutation(
  status: "mfa_required" | "mfa_failed",
  csrfDigest: Uint8Array,
): SessionMutation<BffAuthResult> {
  return {
    action: "replace",
    record: { status, csrfDigest },
    result: simpleResult(status, { kind: "none" }),
  };
}

function failedLoginMutation(
  csrfDigest: Uint8Array,
): SessionMutation<BffAuthResult> {
  return stateMutation("mfa_failed", csrfDigest);
}

function applyRotatedCookie(
  transaction: Readonly<{
    result: BffAuthResult;
    rotatedCookie?: string;
  }>,
): BffAuthResult {
  if (!transaction.rotatedCookie) {
    return transaction.result;
  }
  return {
    ...transaction.result,
    cookie: { kind: "set", value: transaction.rotatedCookie },
  };
}

function authenticatedResolutionMutation(
  record: ServerSessionRecord,
  resolved: ResolvedSession,
  now: Date,
): SessionMutation<BffAuthResult> {
  const result = resultFromEvaluation(
    resolved.evaluation,
    { kind: "none" },
    undefined,
    now,
  );
  if (tokensChanged(record, resolved)) {
    return {
      action: "replace",
      record: authenticatedRecord(record.csrfDigest, resolved.tokens),
      result,
    };
  }
  return { action: "keep", result };
}

function resolvedFailureMutation(
  record: ServerSessionRecord,
  resolved: ResolvedSession,
  now: Date,
): SessionMutation<BffAuthResult> {
  const shouldDelete =
    resolved.evaluation.kind === "login_required" ||
    resolved.evaluation.kind === "malformed";
  const result = resultFromEvaluation(
    resolved.evaluation,
    shouldDelete ? { kind: "clear" } : { kind: "none" },
    undefined,
    now,
  );
  if (shouldDelete) {
    return { action: "delete", result };
  }
  if (tokensChanged(record, resolved)) {
    return {
      action: "replace",
      record: authenticatedRecord(record.csrfDigest, resolved.tokens),
      result,
    };
  }
  return { action: "keep", result };
}

function tokensChanged(
  record: ServerSessionRecord,
  resolved: ResolvedSession,
): boolean {
  return (
    record.status === "authenticated" &&
    (record.tokens.accessToken !== resolved.tokens.accessToken ||
      record.tokens.refreshToken !== resolved.tokens.refreshToken)
  );
}

function authenticatedRecord(
  csrfDigest: Uint8Array,
  tokens: IdentityTokenPair,
): AuthenticatedSessionRecord {
  return { status: "authenticated", csrfDigest, tokens };
}

function parseLoginInput(value: unknown): LoginInput | null {
  if (!isRecord(value)) {
    return null;
  }
  const keys = Object.keys(value).sort();
  const allowed =
    keys.join(",") === "identifier,password,tenantId" ||
    keys.join(",") === "identifier,mfaCode,password,tenantId";
  if (
    !allowed ||
    typeof value.tenantId !== "string" ||
    !isUuid(value.tenantId) ||
    typeof value.identifier !== "string" ||
    value.identifier.length < 1 ||
    value.identifier.length > 254 ||
    typeof value.password !== "string" ||
    value.password.length < 1 ||
    value.password.length > 1024 ||
    (value.mfaCode !== undefined &&
      (typeof value.mfaCode !== "string" || !/^\d{6}$/.test(value.mfaCode)))
  ) {
    return null;
  }
  return {
    tenantId: value.tenantId,
    identifier: value.identifier,
    password: value.password,
    ...(typeof value.mfaCode === "string" ? { mfaCode: value.mfaCode } : {}),
  };
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

function newSecret(): string {
  return randomBytes(32).toString("base64url");
}

function digestSecret(value: string): Uint8Array {
  return createHash("sha256").update(value).digest();
}

function validCsrf(value: unknown, expectedDigest: Uint8Array): boolean {
  return constantTimeCsrfMatch(value, expectedDigest, digestSecret);
}

function isIdentityError(error: unknown, errorCode: string): boolean {
  return error instanceof IdentityGatewayError && error.errorCode === errorCode;
}

function isUnavailableIdentityError(error: unknown): boolean {
  return (
    error instanceof IdentityGatewayError &&
    (error.status >= 500 ||
      error.errorCode === "AUTH_DEPENDENCY_UNAVAILABLE" ||
      error.errorCode === "AUTH_RATE_LIMIT_UNAVAILABLE")
  );
}

async function bestEffortLogout(
  identity: IdentityGateway,
  accessToken: string,
): Promise<void> {
  try {
    await identity.logout(accessToken);
  } catch {
    // Local access remains denied. Runtime logs must not include token or response data.
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
