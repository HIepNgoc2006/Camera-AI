import type {
  BffAuthResult,
  BffAuthService,
} from "@/features/auth/application/bff-auth-service";
import { WEB_BFF_SESSION_POLICY_VERSION } from "@/features/auth/domain/route-access";

const unavailableResult = (): BffAuthResult => ({
  state: {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "unavailable",
    errorCode: "SESSION_UNAVAILABLE",
  },
  cookie: { kind: "none" },
  session: null,
});

/**
 * Production provider wiring and activation are deliberately outside Issue #70.
 * This runtime keeps every route closed until an approved server-side session
 * store, authorization provider, warning profile, and deployment record compose
 * createBffAuthService at the application boundary.
 */
export const inactiveBffAuthService: BffAuthService = {
  prepare: async () => unavailableResult(),
  read: async () => unavailableResult(),
  login: async () => unavailableResult(),
  logout: async () => unavailableResult(),
};
