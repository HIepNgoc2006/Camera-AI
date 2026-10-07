import {
  isUiActionVisible,
  validateAuthenticatedSessionSnapshot,
} from "@/features/auth/domain/route-access";
import type { ViolationActionPermissionCode } from "@/features/violations/domain/violation-view";
import type { AuthorizedViolationSession } from "@/features/violations/application/query-violation";
import type { ViolationActions } from "@/features/violations/domain/violation-view";
import type { ViolationRuntimeCapabilities } from "@/features/violations/application/query-violation";

export interface ResolveViolationActionVisibilityInput {
  readonly session: unknown;
  readonly capabilities: ViolationRuntimeCapabilities;
  readonly now: Date;
}

/**
 * Single action gate for the violation screen: an affordance renders only
 * when the authoritative session grants the exact approved permission AND
 * the matching backend contract/provider is active in this composition.
 * Backend object-level authorization remains the final enforcement.
 */
export function resolveViolationActionVisibility({
  session,
  capabilities,
  now,
}: ResolveViolationActionVisibilityInput): ViolationActions {
  const authorizedSession = validateAuthenticatedSessionSnapshot(session, now);
  if (!authorizedSession) {
    return { canReview: false, canCorrect: false, canExport: false };
  }

  return resolveViolationActionVisibilityForSession(
    authorizedSession,
    capabilities,
    now,
  );
}

export function resolveViolationActionVisibilityForSession(
  session: AuthorizedViolationSession,
  capabilities: ViolationRuntimeCapabilities,
  now: Date,
): ViolationActions {
  if (
    !isUiActionVisible({
      session,
      requiredPermission: "violation.view_metadata",
      now,
    })
  ) {
    return { canReview: false, canCorrect: false, canExport: false };
  }

  const hasPermission = (permission: ViolationActionPermissionCode): boolean =>
    isUiActionVisible({
      session,
      requiredPermission: permission,
      now,
    });

  return {
    canReview: capabilities.reviewActive && hasPermission("violation.review"),
    canCorrect:
      capabilities.correctionActive && hasPermission("violation.correct"),
    canExport: capabilities.exportActive && hasPermission("violation.export"),
  };
}
