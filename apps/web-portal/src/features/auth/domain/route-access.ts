export const AUTHORIZATION_POLICY_VERSION = "rbac_policy_v1" as const;
export const WEB_BFF_SESSION_POLICY_VERSION =
  "web_bff_session_policy_v1" as const;

export const PERMISSION_CODES = [
  "school_profile.view_metadata",
  "school_profile.correct",
  "attendance.view_metadata",
  "attendance.correct",
  "attendance.export",
  "timekeeping.view_metadata",
  "timekeeping.correct",
  "timekeeping.export",
  "violation.view_metadata",
  "violation.review",
  "violation.correct",
  "violation.export",
  "evidence.view_metadata",
  "evidence.view_thumbnail",
  "evidence.view_original",
  "evidence.download",
  "evidence.export",
  "evidence.correct",
  "evidence.review",
  "evidence.delete_request",
  "evidence.hold_request",
  "evidence.hold_approve",
  "consent.view_metadata",
  "consent.correct",
  "role_assignment.view_metadata",
  "role_assignment.correct",
  "report.view_metadata",
  "report.export",
  "audit.view_metadata",
  "audit.export",
  "camera_status.view_metadata",
  "camera_mapping.correct",
  "notification.view_metadata",
  "retention.delete_request",
  "retention.hold_request",
  "retention.hold_approve",
] as const;

export type PermissionCode = (typeof PERMISSION_CODES)[number];

export interface PermissionSnapshot {
  readonly policyVersion: typeof AUTHORIZATION_POLICY_VERSION;
  readonly permissions: readonly PermissionCode[];
}

export interface AuthenticatedSessionSnapshot {
  readonly policyVersion: typeof WEB_BFF_SESSION_POLICY_VERSION;
  readonly status: "authenticated";
  readonly actorId: string;
  readonly tenantId: string;
  readonly schoolId: string;
  readonly mfaState: "verified" | "not_required";
  readonly issuedAt: string;
  readonly absoluteExpiresAt: string;
  readonly inactivityExpiresAt: string;
  readonly warningStartsAt: string;
  readonly authorization: PermissionSnapshot;
}

export type AuthenticatedSessionSnapshotValidation =
  | {
      readonly kind: "active";
      readonly session: AuthenticatedSessionSnapshot;
    }
  | { readonly kind: "expired" }
  | { readonly kind: "invalid" };

export type SessionSnapshot =
  | AuthenticatedSessionSnapshot
  | { readonly status: "unauthenticated" }
  | { readonly status: "unknown" };

interface ProtectedRoutePolicy {
  readonly routeGroup: `/app${string}`;
  readonly includeDescendants: boolean;
  readonly anyPermission: readonly [PermissionCode, ...PermissionCode[]];
}

export const PUBLIC_ROUTES = ["/", "/login", "/not-authorized"] as const;

export const PROTECTED_ROUTE_POLICIES = [
  {
    routeGroup: "/app/access",
    includeDescendants: true,
    anyPermission: ["role_assignment.view_metadata"],
  },
  {
    routeGroup: "/app/attendance",
    includeDescendants: true,
    anyPermission: ["attendance.view_metadata"],
  },
  {
    routeGroup: "/app/audit",
    includeDescendants: true,
    anyPermission: ["audit.view_metadata"],
  },
  {
    routeGroup: "/app/cameras",
    includeDescendants: true,
    anyPermission: ["camera_status.view_metadata"],
  },
  {
    routeGroup: "/app/consent",
    includeDescendants: true,
    anyPermission: ["consent.view_metadata"],
  },
  {
    routeGroup: "/app/evidence",
    includeDescendants: true,
    anyPermission: ["evidence.view_metadata"],
  },
  {
    routeGroup: "/app/notifications",
    includeDescendants: true,
    anyPermission: ["notification.view_metadata"],
  },
  {
    routeGroup: "/app/reports",
    includeDescendants: true,
    anyPermission: ["report.view_metadata"],
  },
  {
    routeGroup: "/app/timekeeping",
    includeDescendants: true,
    anyPermission: ["timekeeping.view_metadata"],
  },
  {
    routeGroup: "/app/violations",
    includeDescendants: true,
    anyPermission: ["violation.view_metadata"],
  },
  {
    routeGroup: "/app",
    includeDescendants: false,
    anyPermission: [
      "school_profile.view_metadata",
      "attendance.view_metadata",
      "timekeeping.view_metadata",
      "violation.view_metadata",
      "evidence.view_metadata",
      "consent.view_metadata",
      "role_assignment.view_metadata",
      "report.view_metadata",
      "audit.view_metadata",
      "camera_status.view_metadata",
      "notification.view_metadata",
    ],
  },
] as const satisfies readonly ProtectedRoutePolicy[];

export type RouteAccessDecision =
  | { readonly kind: "allow" }
  | {
      readonly kind: "redirect";
      readonly destination: "/login" | "/not-authorized";
      readonly reason: "auth-required" | "forbidden" | "route-not-allowed";
    };

export interface RouteAccessRequest {
  readonly pathname: string;
  readonly session: unknown;
  readonly now?: Date;
}

export interface UiActionVisibilityRequest {
  readonly session: unknown;
  readonly requiredPermission: PermissionCode;
  readonly now?: Date;
}

const PUBLIC_ROUTE_SET = new Set<string>(PUBLIC_ROUTES);
const PERMISSION_CODE_SET = new Set<string>(PERMISSION_CODES);
const MAX_ACTOR_ID_LENGTH = 128;
const MAX_PERMISSION_COUNT = PERMISSION_CODES.length;
const MAX_PATHNAME_LENGTH = 2_048;
const REDIRECT_DESTINATION_BY_REASON = {
  "auth-required": "/login",
  forbidden: "/not-authorized",
  "route-not-allowed": "/not-authorized",
} as const;

export function resolveRouteAccess({
  pathname,
  session,
  now = new Date(),
}: RouteAccessRequest): RouteAccessDecision {
  if (PUBLIC_ROUTE_SET.has(pathname)) {
    return { kind: "allow" };
  }

  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );
  if (!authenticatedSession) {
    return {
      kind: "redirect",
      destination: "/login",
      reason: "auth-required",
    };
  }

  const routePolicy = findProtectedRoutePolicy(pathname);
  if (!routePolicy) {
    return {
      kind: "redirect",
      destination: "/not-authorized",
      reason: "route-not-allowed",
    };
  }

  if (
    !routePolicy.anyPermission.some((permission) =>
      authenticatedSession.authorization.permissions.includes(permission),
    )
  ) {
    return {
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    };
  }

  return { kind: "allow" };
}

export function isUiActionVisible({
  session,
  requiredPermission,
  now = new Date(),
}: UiActionVisibilityRequest): boolean {
  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );

  return (
    authenticatedSession?.authorization.permissions.includes(
      requiredPermission,
    ) ?? false
  );
}

export function buildInternalRedirect(
  decision: Extract<RouteAccessDecision, { readonly kind: "redirect" }>,
): string {
  const reason = isRedirectReason(decision.reason)
    ? decision.reason
    : "auth-required";
  const destination = REDIRECT_DESTINATION_BY_REASON[reason];
  const search = new URLSearchParams({ reason });
  return `${destination}?${search.toString()}`;
}

export function validateAuthenticatedSessionSnapshot(
  session: unknown,
  now: Date,
): AuthenticatedSessionSnapshot | null {
  const validation = evaluateAuthenticatedSessionSnapshot(session, now);
  return validation.kind === "active" ? validation.session : null;
}

export function evaluateAuthenticatedSessionSnapshot(
  session: unknown,
  now: Date,
): AuthenticatedSessionSnapshotValidation {
  if (
    !isRecord(session) ||
    !hasExactKeys(session, [
      "absoluteExpiresAt",
      "actorId",
      "authorization",
      "inactivityExpiresAt",
      "issuedAt",
      "mfaState",
      "policyVersion",
      "schoolId",
      "status",
      "tenantId",
      "warningStartsAt",
    ]) ||
    session.policyVersion !== WEB_BFF_SESSION_POLICY_VERSION ||
    session.status !== "authenticated"
  ) {
    return { kind: "invalid" };
  }

  if (
    !isOpaqueIdentifier(session.actorId) ||
    !isOpaqueIdentifier(session.tenantId) ||
    !isOpaqueIdentifier(session.schoolId) ||
    (session.mfaState !== "verified" && session.mfaState !== "not_required")
  ) {
    return { kind: "invalid" };
  }

  const authorization = session.authorization;
  if (
    !isRecord(authorization) ||
    !hasExactKeys(authorization, ["permissions", "policyVersion"]) ||
    authorization.policyVersion !== AUTHORIZATION_POLICY_VERSION ||
    !isValidPermissionSnapshot(authorization.permissions)
  ) {
    return { kind: "invalid" };
  }

  const timeline = evaluateSessionTimeline(session, now);
  if (timeline === "invalid") {
    return { kind: "invalid" };
  }
  if (timeline === "expired") {
    return { kind: "expired" };
  }

  return {
    kind: "active",
    session: session as unknown as AuthenticatedSessionSnapshot,
  };
}

function isOpaqueIdentifier(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= MAX_ACTOR_ID_LENGTH &&
    value.trim() === value &&
    /^[A-Za-z0-9._:-]+$/u.test(value)
  );
}

function evaluateSessionTimeline(
  session: Record<string, unknown>,
  now: Date,
): "active" | "expired" | "invalid" {
  if (!Number.isFinite(now.getTime())) {
    return "invalid";
  }

  const issuedAt = parseUtcInstant(session.issuedAt);
  const absoluteExpiresAt = parseUtcInstant(session.absoluteExpiresAt);
  const inactivityExpiresAt = parseUtcInstant(session.inactivityExpiresAt);
  const warningStartsAt = parseUtcInstant(session.warningStartsAt);
  if (
    issuedAt === null ||
    absoluteExpiresAt === null ||
    inactivityExpiresAt === null ||
    warningStartsAt === null
  ) {
    return "invalid";
  }

  const nowTime = now.getTime();
  const effectiveExpiry = Math.min(absoluteExpiresAt, inactivityExpiresAt);
  if (
    issuedAt > nowTime ||
    warningStartsAt < issuedAt ||
    warningStartsAt >= effectiveExpiry
  ) {
    return "invalid";
  }

  return nowTime < effectiveExpiry ? "active" : "expired";
}

function parseUtcInstant(value: unknown): number | null {
  if (
    typeof value !== "string" ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u.test(value)
  ) {
    return null;
  }

  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value
    ? parsed
    : null;
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return (
    keys.length === sortedExpected.length &&
    keys.every((key, index) => key === sortedExpected[index])
  );
}

function findProtectedRoutePolicy(
  pathname: string,
): ProtectedRoutePolicy | undefined {
  if (!isSafeInternalPathname(pathname)) {
    return undefined;
  }

  return PROTECTED_ROUTE_POLICIES.find(
    ({ routeGroup, includeDescendants }) =>
      pathname === routeGroup ||
      (includeDescendants && pathname.startsWith(`${routeGroup}/`)),
  );
}

function isSafeInternalPathname(pathname: string): boolean {
  if (
    pathname.length === 0 ||
    pathname.length > MAX_PATHNAME_LENGTH ||
    !pathname.startsWith("/") ||
    pathname.includes("//") ||
    pathname.includes("\\") ||
    pathname.includes("?") ||
    pathname.includes("#") ||
    /[\u0000-\u001f\u007f]/u.test(pathname)
  ) {
    return false;
  }

  const normalized = pathname.toLowerCase();
  if (
    normalized.includes("%2f") ||
    normalized.includes("%5c") ||
    normalized.includes("%2e")
  ) {
    return false;
  }

  return !pathname
    .split("/")
    .some((segment) => segment === "." || segment === "..");
}

function isPermissionCode(value: unknown): value is PermissionCode {
  return typeof value === "string" && PERMISSION_CODE_SET.has(value);
}

function isValidPermissionSnapshot(
  value: unknown,
): value is readonly PermissionCode[] {
  if (!Array.isArray(value) || value.length > MAX_PERMISSION_COUNT) {
    return false;
  }

  const permissions = new Set<PermissionCode>();
  for (let index = 0; index < value.length; index += 1) {
    if (!Object.hasOwn(value, index) || !isPermissionCode(value[index])) {
      return false;
    }

    permissions.add(value[index]);
  }

  return permissions.size === value.length;
}

function isRedirectReason(
  value: unknown,
): value is keyof typeof REDIRECT_DESTINATION_BY_REASON {
  return (
    typeof value === "string" &&
    Object.hasOwn(REDIRECT_DESTINATION_BY_REASON, value)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
