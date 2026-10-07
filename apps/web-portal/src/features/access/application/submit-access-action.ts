import type { AccessMutationKind } from "@/features/access/domain/access-view";

export interface AccessMutationRequest {
  readonly assignmentId: string;
  readonly kind: AccessMutationKind;
  /** Server-assigned row version the proposal was based on. */
  readonly expectedVersion: number;
  /** Server-resolved grant set reference; never client-supplied role data. */
  readonly grantRef: string;
}

export type AccessMutationSubmitResult =
  | { readonly kind: "denied" }
  | { readonly kind: "validation" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "ACCESS_MUTATION_INACTIVE" | "ACCESS_MUTATION_UPSTREAM_UNAVAILABLE";
    }
  | {
      readonly kind: "accepted";
      readonly proposal: {
        readonly changeRef: string;
        /** A submitted change is never granted until separately approved. */
        readonly state: "pending_approval";
      };
    };

export interface AccessMutationSubmitProvider {
  submit(
    input: Readonly<{
      request: AccessMutationRequest;
      scope: Readonly<{
        tenantId: string;
        schoolId: string;
        actorId: string;
      }>;
    }>,
  ): Promise<AccessMutationSubmitResult>;
}

/**
 * Issue #75 ships the access mutation action fail-closed. The approved
 * contract defines `POST /api/v1/role-assignments/{id}/changes` under
 * dual-control `role_assignment.correct`; no approved runtime activation
 * exists in this composition, so the checked-in provider denies every
 * submission. Approve and revoke have no approved mapping at all and are
 * rejected before any provider call; self-approval is structurally
 * impossible because no actor can both initiate and approve in this model.
 */
export const inactiveAccessMutationProvider: AccessMutationSubmitProvider = {
  submit: async () => ({
    kind: "unavailable",
    errorCode: "ACCESS_MUTATION_INACTIVE",
  }),
};
