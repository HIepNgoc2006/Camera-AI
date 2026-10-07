import type { ConsentMutationKind } from "@/features/consent/domain/consent-view";

export interface ConsentMutationRequest {
  readonly consentId: string;
  readonly kind: ConsentMutationKind;
  /** Server-assigned row version the decision was based on. */
  readonly expectedVersion: number;
  /** Approved decision label from the server allowlist, never free text. */
  readonly decisionCode: string;
}

export type ConsentMutationSubmitResult =
  | { readonly kind: "denied" }
  | { readonly kind: "validation" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "CONSENT_MUTATION_INACTIVE" | "CONSENT_MUTATION_UPSTREAM_UNAVAILABLE";
    }
  | {
      readonly kind: "accepted";
      readonly decision: {
        readonly decisionRef: string;
        /** The decision is durable only after the backend audit commit. */
        readonly state: "recorded";
      };
    };

export interface ConsentMutationSubmitProvider {
  submit(
    input: Readonly<{
      request: ConsentMutationRequest;
      scope: Readonly<{
        tenantId: string;
        schoolId: string;
        actorId: string;
      }>;
    }>,
  ): Promise<ConsentMutationSubmitResult>;
}

/**
 * Issue #76 ships the consent mutation action fail-closed. The approved
 * contract defines `POST /api/v1/consents/{id}/decisions` under
 * `consent.correct`; no approved runtime activation exists in this
 * composition, so the checked-in provider denies every submission.
 * Withdrawal requests map to `privacy.withdrawal.request.*` codes outside
 * `rbac_policy_v1` and are rejected before any provider call; guardian and
 * maturity authority are backend checks that a UI confirmation can never
 * confer. The UI never deletes media or database rows directly.
 */
export const inactiveConsentMutationProvider: ConsentMutationSubmitProvider = {
  submit: async () => ({
    kind: "unavailable",
    errorCode: "CONSENT_MUTATION_INACTIVE",
  }),
};
