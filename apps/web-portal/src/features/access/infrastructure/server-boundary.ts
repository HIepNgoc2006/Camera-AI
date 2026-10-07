import "server-only";

import type {
  AccessReadProvider,
  AccessRuntimeCapabilities,
} from "@/features/access/application/query-access";

export const inactiveAccessCapabilities: AccessRuntimeCapabilities = {
  readActive: false,
  mutationActive: false,
};

/**
 * Issue #75 ships without an active API Gateway access read contract. The
 * approved baseline defines only `GET /api/v1/role-assignments/{id}` and
 * `POST /api/v1/role-assignments/{id}/changes` (bearer + MFA) with no list
 * operation; synthetic success providers belong in tests only. Mutation
 * submission stays denied until `role_assignment.correct` has an approved
 * dual-control runtime.
 */
export const inactiveAccessReadProvider: AccessReadProvider = {
  readList: async () => ({
    kind: "unavailable",
    errorCode: "ACCESS_RUNTIME_INACTIVE",
  }),
};

export function getAccessServerBoundary(): {
  readonly provider: AccessReadProvider;
  readonly capabilities: AccessRuntimeCapabilities;
} {
  return {
    provider: inactiveAccessReadProvider,
    capabilities: inactiveAccessCapabilities,
  };
}
