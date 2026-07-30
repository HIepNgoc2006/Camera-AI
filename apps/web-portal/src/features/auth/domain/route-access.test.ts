import { describe, expect, it } from "vitest";

import { resolveRouteAccess } from "./route-access";

describe("resolveRouteAccess", () => {
  it.each(["/", "/login", "/not-authorized"])(
    "allows public route %s without a session",
    (pathname) => {
      expect(resolveRouteAccess({ pathname, session: null })).toEqual({
        kind: "allow",
      });
    },
  );

  it.each([null, undefined, { status: "unknown" as const }])(
    "denies protected routes when session state is %j",
    (session) => {
      expect(resolveRouteAccess({ pathname: "/app", session })).toEqual({
        kind: "redirect",
        destination: "/login",
        reason: "auth-required",
      });
    },
  );

  it("allows an authenticated session through the guarded shell", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app",
        session: { status: "authenticated", actorId: "actor_fake_001" },
      }),
    ).toEqual({ kind: "allow" });
  });

  it("denies authenticated actors without a required role", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/admin",
        session: { status: "authenticated", roles: ["teacher"] },
        requiredRoles: ["school_admin"],
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
  });
});
