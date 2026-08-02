import type { SessionSnapshot } from "@/features/auth/domain/route-access";

/**
 * Identity integration is intentionally absent from the skeleton.
 *
 * Returning null keeps every protected route closed until Issue #70 replaces
 * this seam with a server-only reader for web_bff_session_policy_v1. Cookie
 * presence alone is never converted into an authenticated snapshot.
 */
export async function readSessionSnapshot(): Promise<SessionSnapshot | null> {
  return null;
}
