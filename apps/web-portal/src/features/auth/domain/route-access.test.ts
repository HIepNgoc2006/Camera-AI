import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  buildInternalRedirect,
  isUiActionVisible,
  PERMISSION_CODES,
  PROTECTED_ROUTE_POLICIES,
  resolveRouteAccess,
  WEB_BFF_SESSION_POLICY_VERSION,
  type PermissionCode,
  type SessionSnapshot,
} from "./route-access";

interface CatalogFile {
  readonly policy_version: string;
  readonly permissions: readonly {
    readonly permission_code: string;
  }[];
}

const FAKE_ACTOR_ID = "actor_fake_001";
const SPARSE_PERMISSIONS = new Array<PermissionCode>(2);
SPARSE_PERMISSIONS[1] = "report.view_metadata";

function fakeAuthenticatedSession(
  permissions: readonly PermissionCode[],
): SessionSnapshot {
  return {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "authenticated",
    actorId: FAKE_ACTOR_ID,
    tenantId: "tenant_test_001",
    schoolId: "school_test_001",
    mfaState: "verified",
    issuedAt: "2020-01-01T00:00:00.000Z",
    warningStartsAt: "2098-12-31T23:00:00.000Z",
    inactivityExpiresAt: "2099-01-01T00:00:00.000Z",
    absoluteExpiresAt: "2099-02-01T00:00:00.000Z",
    authorization: {
      policyVersion: AUTHORIZATION_POLICY_VERSION,
      permissions,
    },
  };
}

describe("authorization catalog alignment", () => {
  it("uses only permission codes from the tracked authorization catalog", () => {
    const catalogPath = fileURLToPath(
      new URL(
        "../../../../../../packages/authorization-policy/permission-catalog-v1.json",
        import.meta.url,
      ),
    );
    const catalog = JSON.parse(
      readFileSync(catalogPath, "utf8"),
    ) as CatalogFile;
    const catalogPermissions = new Set(
      catalog.permissions.map(({ permission_code }) => permission_code),
    );

    expect(catalog.policy_version).toBe(AUTHORIZATION_POLICY_VERSION);
    expect(new Set(PERMISSION_CODES)).toEqual(catalogPermissions);
    for (const policy of PROTECTED_ROUTE_POLICIES) {
      for (const permission of policy.anyPermission) {
        expect(catalogPermissions.has(permission)).toBe(true);
      }
    }
  });
});

describe("resolveRouteAccess", () => {
  it.each(["/", "/login", "/not-authorized"])(
    "allows explicitly public route %s without a session",
    (pathname) => {
      expect(resolveRouteAccess({ pathname, session: null })).toEqual({
        kind: "allow",
      });
    },
  );

  it.each([
    null,
    undefined,
    { status: "unknown" },
    { status: "unauthenticated" },
  ])("redirects missing or unauthenticated state %j to login", (session) => {
    expect(resolveRouteAccess({ pathname: "/app", session })).toEqual({
      kind: "redirect",
      destination: "/login",
      reason: "auth-required",
    });
  });

  it.each([
    {},
    { status: "authenticated" },
    {
      status: "authenticated",
      actorId: "",
      authorization: {
        policyVersion: AUTHORIZATION_POLICY_VERSION,
        permissions: ["report.view_metadata"],
      },
    },
    {
      status: "authenticated",
      actorId: FAKE_ACTOR_ID,
      authorization: {
        policyVersion: "unknown_policy",
        permissions: ["report.view_metadata"],
      },
    },
    {
      status: "authenticated",
      actorId: FAKE_ACTOR_ID,
      authorization: {
        policyVersion: AUTHORIZATION_POLICY_VERSION,
        permissions: ["unknown.permission"],
      },
    },
    {
      status: "authenticated",
      actorId: FAKE_ACTOR_ID,
      authorization: {
        policyVersion: AUTHORIZATION_POLICY_VERSION,
        permissions: ["report.view_metadata", "report.view_metadata"],
      },
    },
    {
      status: "authenticated",
      actorId: FAKE_ACTOR_ID,
      authorization: {
        policyVersion: AUTHORIZATION_POLICY_VERSION,
        permissions: SPARSE_PERMISSIONS,
      },
    },
  ])("fails malformed session state closed to login", (session) => {
    expect(resolveRouteAccess({ pathname: "/app", session })).toEqual({
      kind: "redirect",
      destination: "/login",
      reason: "auth-required",
    });
  });

  it("fails closed at the authoritative inactivity-expiry boundary", () => {
    const session = {
      ...fakeAuthenticatedSession(["attendance.view_metadata"]),
      warningStartsAt: "2026-08-02T02:30:00.000Z",
      inactivityExpiresAt: "2026-08-02T03:00:00.000Z",
      absoluteExpiresAt: "2026-08-02T04:00:00.000Z",
    };

    expect(
      resolveRouteAccess({
        pathname: "/app",
        session,
        now: new Date("2026-08-02T03:00:00.000Z"),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/login",
      reason: "auth-required",
    });
  });

  it("allows an authenticated actor with the route permission", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/attendance/daily",
        session: fakeAuthenticatedSession(["attendance.view_metadata"]),
      }),
    ).toEqual({ kind: "allow" });
  });

  it("allows the violations route only with the violation view permission", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/violations",
        session: fakeAuthenticatedSession(["violation.view_metadata"]),
      }),
    ).toEqual({ kind: "allow" });
    expect(
      resolveRouteAccess({
        pathname: "/app/violations",
        session: fakeAuthenticatedSession(["report.view_metadata"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
  });

  it("allows the reports route only with the report view permission", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/reports",
        session: fakeAuthenticatedSession(["report.view_metadata"]),
      }),
    ).toEqual({ kind: "allow" });
    expect(
      resolveRouteAccess({
        pathname: "/app/reports",
        session: fakeAuthenticatedSession(["attendance.view_metadata"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
  });

  it("allows the access route only with the role assignment view permission", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/access",
        session: fakeAuthenticatedSession(["role_assignment.view_metadata"]),
      }),
    ).toEqual({ kind: "allow" });
    expect(
      resolveRouteAccess({
        pathname: "/app/access",
        session: fakeAuthenticatedSession(["report.view_metadata"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
    expect(
      resolveRouteAccess({
        pathname: "/app/access/users/00000000-0000-4000-8000-000000000001",
        session: fakeAuthenticatedSession(["violation.review"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
  });

  it("allows the consent route only with the consent view permission", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/consent",
        session: fakeAuthenticatedSession(["consent.view_metadata"]),
      }),
    ).toEqual({ kind: "allow" });
    expect(
      resolveRouteAccess({
        pathname: "/app/consent/00000000-0000-4000-8000-00000000007c",
        session: fakeAuthenticatedSession(["report.view_metadata"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
    expect(
      resolveRouteAccess({
        pathname: "/app/consent",
        session: fakeAuthenticatedSession(["consent.correct"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
  });

  it("allows the protected shell for any recognized Web view permission", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app",
        session: fakeAuthenticatedSession(["attendance.view_metadata"]),
      }),
    ).toEqual({ kind: "allow" });
  });

  it("denies an authenticated actor without the route permission", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/attendance",
        session: fakeAuthenticatedSession(["report.view_metadata"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
  });

  it.each([
    "/app/unknown",
    "/unclassified",
    "/login/",
    "https://attacker.example/path",
    "//attacker.example/path",
    "/app/%2e%2e/login",
    "/app\\reports",
  ])("denies unknown or unsafe route %s by default", (pathname) => {
    expect(
      resolveRouteAccess({
        pathname,
        session: fakeAuthenticatedSession(["report.view_metadata"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "route-not-allowed",
    });
  });

  it("does not let a broad route group override a more specific group", () => {
    expect(
      resolveRouteAccess({
        pathname: "/app/audit",
        session: fakeAuthenticatedSession(["report.view_metadata"]),
      }),
    ).toEqual({
      kind: "redirect",
      destination: "/not-authorized",
      reason: "forbidden",
    });
  });

  it.each(PROTECTED_ROUTE_POLICIES)(
    "allows only the mapped permission for $routeGroup",
    (policy) => {
      const pathname = policy.includeDescendants
        ? `${policy.routeGroup}/fake-child`
        : policy.routeGroup;
      const allowedPermission = policy.anyPermission[0];
      const unrelatedPermission = PERMISSION_CODES.find(
        (permission) =>
          !(policy.anyPermission as readonly PermissionCode[]).includes(
            permission,
          ),
      );

      expect(unrelatedPermission).toBeDefined();
      expect(
        resolveRouteAccess({
          pathname,
          session: fakeAuthenticatedSession([allowedPermission]),
        }),
      ).toEqual({ kind: "allow" });
      expect(
        resolveRouteAccess({
          pathname,
          session: fakeAuthenticatedSession([unrelatedPermission!]),
        }),
      ).toEqual({
        kind: "redirect",
        destination: "/not-authorized",
        reason: "forbidden",
      });
    },
  );
});

describe("isUiActionVisible", () => {
  it("shows an action only when the validated snapshot has its permission", () => {
    const session = fakeAuthenticatedSession(["violation.review"]);

    expect(
      isUiActionVisible({
        session,
        requiredPermission: "violation.review",
      }),
    ).toBe(true);
    expect(
      isUiActionVisible({
        session,
        requiredPermission: "violation.export",
      }),
    ).toBe(false);
  });

  it.each([
    null,
    { status: "unknown" },
    {
      status: "authenticated",
      actorId: FAKE_ACTOR_ID,
      authorization: {
        policyVersion: "unknown_policy",
        permissions: ["violation.review"],
      },
    },
  ])("hides actions for absent, unknown or malformed state", (session) => {
    expect(
      isUiActionVisible({
        session,
        requiredPermission: "violation.review",
      }),
    ).toBe(false);
  });
});

describe("buildInternalRedirect", () => {
  it.each([
    {
      kind: "redirect" as const,
      destination: "/login" as const,
      reason: "auth-required" as const,
    },
    {
      kind: "redirect" as const,
      destination: "/not-authorized" as const,
      reason: "forbidden" as const,
    },
    {
      kind: "redirect" as const,
      destination: "/not-authorized" as const,
      reason: "route-not-allowed" as const,
    },
  ])("builds only an allowlisted same-origin location", (decision) => {
    const location = buildInternalRedirect(decision);
    const resolved = new URL(location, "https://portal.example.invalid");

    expect(location.startsWith("/")).toBe(true);
    expect(location.startsWith("//")).toBe(false);
    expect(resolved.origin).toBe("https://portal.example.invalid");
    expect(resolved.searchParams.get("reason")).toBe(decision.reason);
    expect(resolved.searchParams.has("returnTo")).toBe(false);
  });

  it("ignores a forged external destination at the runtime boundary", () => {
    const forgedDecision = {
      kind: "redirect",
      destination: "https://attacker.example",
      reason: "forbidden",
    } as unknown as Parameters<typeof buildInternalRedirect>[0];

    expect(buildInternalRedirect(forgedDecision)).toBe(
      "/not-authorized?reason=forbidden",
    );
  });

  it("fails a forged reason closed to the login redirect", () => {
    const forgedDecision = {
      kind: "redirect",
      destination: "https://attacker.example",
      reason: "__proto__",
    } as unknown as Parameters<typeof buildInternalRedirect>[0];

    expect(buildInternalRedirect(forgedDecision)).toBe(
      "/login?reason=auth-required",
    );
  });
});
