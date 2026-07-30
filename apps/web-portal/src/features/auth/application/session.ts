import type { SessionSnapshot } from "@/features/auth/domain/route-access";

/**
 * Identity integration is intentionally absent from the skeleton.
 *
 * Returning null keeps every protected route closed until a later issue
 * replaces this seam with a server-side, validated session reader.
 */
export async function readSessionSnapshot(): Promise<SessionSnapshot | null> {
  return null;
}
