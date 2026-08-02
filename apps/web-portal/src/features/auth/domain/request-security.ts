import { timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE_VALUE_PATTERN = /^[A-Za-z0-9_-]{43,128}$/;
export const CSRF_VALUE_PATTERN = /^[A-Za-z0-9_-]{43,128}$/;

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export type SessionCookieProfile = Readonly<{
  name: string;
  secure: boolean;
}>;

export function parseExpectedOrigin(value: string | undefined): string | null {
  if (!value || value.trim() !== value) {
    return null;
  }

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return null;
  }

  if (
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    parsed.pathname !== "/" ||
    !["http:", "https:"].includes(parsed.protocol) ||
    (parsed.protocol === "http:" && !LOOPBACK_HOSTS.has(parsed.hostname))
  ) {
    return null;
  }

  return parsed.origin;
}

export function parseSessionCookieProfile(
  name: string | undefined,
  expectedOrigin: string | null,
): SessionCookieProfile | null {
  if (
    !name ||
    !expectedOrigin ||
    name.trim() !== name ||
    !/^[A-Za-z0-9_-]{1,96}$/.test(name)
  ) {
    return null;
  }

  const origin = new URL(expectedOrigin);
  const secure = origin.protocol === "https:";
  if (secure ? !name.startsWith("__Host-") : name.startsWith("__Host-")) {
    return null;
  }

  return { name, secure };
}

export function isExpectedUnsafeOrigin(
  originHeader: string | null,
  expectedOrigin: string | null,
): boolean {
  return expectedOrigin !== null && originHeader === expectedOrigin;
}

export function readOpaqueSessionCookie(
  cookieHeader: string | null,
  cookieName: string,
): string | null {
  if (!cookieHeader || cookieHeader.length > 4096) {
    return null;
  }

  const matches: string[] = [];
  for (const part of cookieHeader.split(";")) {
    const separator = part.indexOf("=");
    if (separator < 1 || part.slice(0, separator).trim() !== cookieName) {
      continue;
    }
    matches.push(part.slice(separator + 1).trim());
  }

  if (matches.length !== 1 || !SESSION_COOKIE_VALUE_PATTERN.test(matches[0]!)) {
    return null;
  }
  return matches[0]!;
}

export function serializeSessionCookie(
  profile: SessionCookieProfile,
  value: string,
): string {
  if (!SESSION_COOKIE_VALUE_PATTERN.test(value)) {
    throw new Error("BFF_SESSION_COOKIE_VALUE_INVALID");
  }
  return `${profile.name}=${value}; Path=/; HttpOnly; SameSite=Strict${
    profile.secure ? "; Secure" : ""
  }`;
}

export function serializeClearedSessionCookie(
  profile: SessionCookieProfile,
): string {
  return `${profile.name}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT${
    profile.secure ? "; Secure" : ""
  }`;
}

export function constantTimeCsrfMatch(
  presented: unknown,
  expectedDigest: Uint8Array,
  digest: (value: string) => Uint8Array,
): boolean {
  if (typeof presented !== "string" || !CSRF_VALUE_PATTERN.test(presented)) {
    return false;
  }
  const candidate = digest(presented);
  return (
    candidate.byteLength === expectedDigest.byteLength &&
    timingSafeEqual(candidate, expectedDigest)
  );
}
