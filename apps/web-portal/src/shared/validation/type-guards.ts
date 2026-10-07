/**
 * Canonical object guard for untrusted parsed data in the web portal.
 * Project rule ts-no-local-is-record: this is the single exported definition;
 * feature modules import it instead of redefining a local copy.
 */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
