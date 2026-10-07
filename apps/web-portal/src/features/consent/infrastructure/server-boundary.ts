import "server-only";

import type {
  ConsentReadProvider,
  ConsentRuntimeCapabilities,
} from "@/features/consent/application/query-consent";

export const inactiveConsentCapabilities: ConsentRuntimeCapabilities = {
  readActive: false,
  mutationActive: false,
};

/**
 * Issue #76 ships without an active API Gateway consent list contract. The
 * approved baseline defines only `GET /api/v1/consents/{id}` and `POST
 * /api/v1/consents/{id}/decisions` with no list operation; synthetic
 * success providers belong in tests only. Withdrawal requests additionally
 * require `privacy.withdrawal.request.*` codes outside `rbac_policy_v1`
 * and stay denied until the policy owner approves a mapping.
 */
export const inactiveConsentReadProvider: ConsentReadProvider = {
  readList: async () => ({
    kind: "unavailable",
    errorCode: "CONSENT_RUNTIME_INACTIVE",
  }),
};

export function getConsentServerBoundary(): {
  readonly provider: ConsentReadProvider;
  readonly capabilities: ConsentRuntimeCapabilities;
} {
  return {
    provider: inactiveConsentReadProvider,
    capabilities: inactiveConsentCapabilities,
  };
}
