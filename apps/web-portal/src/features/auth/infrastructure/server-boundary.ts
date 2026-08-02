import "server-only";

import type { BffAuthService } from "@/features/auth/application/bff-auth-service";
import {
  parseExpectedOrigin,
  parseSessionCookieProfile,
  type SessionCookieProfile,
} from "@/features/auth/domain/request-security";
import { inactiveBffAuthService } from "@/features/auth/infrastructure/inactive-runtime";

export type ServerBffBoundary = Readonly<{
  service: BffAuthService;
  expectedOrigin: string | null;
  cookieProfile: SessionCookieProfile | null;
}>;

export function getServerBffBoundary(): ServerBffBoundary {
  const expectedOrigin = parseExpectedOrigin(
    process.env.WEB_BFF_EXPECTED_ORIGIN,
  );
  return {
    service: inactiveBffAuthService,
    expectedOrigin,
    cookieProfile: parseSessionCookieProfile(
      process.env.WEB_BFF_SESSION_COOKIE_NAME,
      expectedOrigin,
    ),
  };
}
