export type AuthStatus = "authenticated" | "unauthenticated" | "unknown";

export interface SessionSnapshot {
  readonly status: AuthStatus;
  readonly actorId?: string;
  readonly roles?: readonly string[];
}

export type RouteAccessDecision =
  | { readonly kind: "allow" }
  | {
      readonly kind: "redirect";
      readonly destination: "/login" | "/not-authorized";
      readonly reason: "auth-required" | "forbidden";
    };

export interface RouteAccessRequest {
  readonly pathname: string;
  readonly session: SessionSnapshot | null | undefined;
  readonly requiredRoles?: readonly string[];
}

const PUBLIC_ROUTES = new Set(["/", "/login", "/not-authorized"]);

export function resolveRouteAccess({
  pathname,
  session,
  requiredRoles = [],
}: RouteAccessRequest): RouteAccessDecision {
  if (PUBLIC_ROUTES.has(pathname)) {
    return { kind: "allow" };
  }

  if (!session || session.status !== "authenticated") {
    return {
      kind: "redirect",
      destination: "/login",
      reason: "auth-required",
    };
  }

  if (
    requiredRoles.length > 0 &&
    !requiredRoles.some((role) => session.roles?.includes(role))
  ) {
    return {
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    };
  }

  return { kind: "allow" };
}
