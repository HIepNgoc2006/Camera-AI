export const AUTHORIZATION_POLICY_VERSION = "rbac_policy_v1" as const;

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
  readonly status: "authenticated";
  readonly actorId: string;
  readonly authorization: PermissionSnapshot;
}

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
}

export interface UiActionVisibilityRequest {
  readonly session: unknown;
  readonly requiredPermission: PermissionCode;
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
}: RouteAccessRequest): RouteAccessDecision {
  if (PUBLIC_ROUTE_SET.has(pathname)) {
    return { kind: "allow" };
  }

  const authenticatedSession = parseAuthenticatedSession(session);
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
}: UiActionVisibilityRequest): boolean {
  const authenticatedSession = parseAuthenticatedSession(session);

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

function parseAuthenticatedSession(
  session: unknown,
): AuthenticatedSessionSnapshot | null {
  if (!isRecord(session) || session.status !== "authenticated") {
    return null;
  }

  if (
    typeof session.actorId !== "string" ||
    session.actorId.length === 0 ||
    session.actorId.length > MAX_ACTOR_ID_LENGTH ||
    session.actorId.trim() !== session.actorId
  ) {
    return null;
  }

  const authorization = session.authorization;
  if (
    !isRecord(authorization) ||
    authorization.policyVersion !== AUTHORIZATION_POLICY_VERSION ||
    !Array.isArray(authorization.permissions) ||
    authorization.permissions.length > MAX_PERMISSION_COUNT ||
    !authorization.permissions.every(isPermissionCode) ||
    new Set(authorization.permissions).size !== authorization.permissions.length
  ) {
    return null;
  }

  return session as unknown as AuthenticatedSessionSnapshot;
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
