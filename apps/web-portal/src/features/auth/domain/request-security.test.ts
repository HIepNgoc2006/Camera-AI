import { createHash, randomBytes } from "node:crypto";

import { describe, expect, it } from "vitest";

import {
  constantTimeCsrfMatch,
  isExpectedUnsafeOrigin,
  parseExpectedOrigin,
  parseSessionCookieProfile,
  readOpaqueSessionCookie,
  serializeClearedSessionCookie,
  serializeSessionCookie,
} from "./request-security";

describe("BFF request security", () => {
  it.each([
    undefined,
    "",
    " https://web.example.invalid/",
    "http://web.example.invalid/",
    "https://user:web.example.invalid/",
    "https://web.example.invalid/path",
    "https://web.example.invalid/?state=unsafe",
  ])("rejects an absent or unsafe expected origin", (value) => {
    expect(parseExpectedOrigin(value)).toBeNull();
  });

  it("accepts HTTPS and loopback development origins only", () => {
    expect(parseExpectedOrigin("https://web.example.invalid/")).toBe(
      "https://web.example.invalid",
    );
    expect(parseExpectedOrigin("http://127.0.0.1:3000/")).toBe(
      "http://127.0.0.1:3000",
    );
  });

  it("requires separate secure and loopback cookie names", () => {
    expect(
      parseSessionCookieProfile(
        "__Host-camera-ai-session",
        "https://web.example.invalid",
      ),
    ).toEqual({ name: "__Host-camera-ai-session", secure: true });
    expect(
      parseSessionCookieProfile(
        "camera-ai-loopback-session",
        "http://localhost:3000",
      ),
    ).toEqual({ name: "camera-ai-loopback-session", secure: false });
    expect(
      parseSessionCookieProfile(
        "camera-ai-session",
        "https://web.example.invalid",
      ),
    ).toBeNull();
    expect(
      parseSessionCookieProfile(
        "__Host-camera-ai-session",
        "http://localhost:3000",
      ),
    ).toBeNull();
  });

  it("requires an exact, non-null Origin for unsafe requests", () => {
    const expected = "https://web.example.invalid";
    expect(isExpectedUnsafeOrigin(expected, expected)).toBe(true);
    expect(isExpectedUnsafeOrigin(null, expected)).toBe(false);
    expect(isExpectedUnsafeOrigin("null", expected)).toBe(false);
    expect(
      isExpectedUnsafeOrigin("https://other.example.invalid", expected),
    ).toBe(false);
  });

  it("rejects duplicate, malformed, or oversized cookie input", () => {
    const value = randomBytes(32).toString("base64url");
    expect(readOpaqueSessionCookie(`sid=${value}`, "sid")).toBe(value);
    expect(
      readOpaqueSessionCookie(`sid=${value}; sid=${value}`, "sid"),
    ).toBeNull();
    expect(readOpaqueSessionCookie("sid=readable", "sid")).toBeNull();
    expect(
      readOpaqueSessionCookie(`sid=${"a".repeat(4097)}`, "sid"),
    ).toBeNull();
  });

  it("serializes host-only HttpOnly Strict cookies without invented lifetime", () => {
    const value = randomBytes(32).toString("base64url");
    const header = serializeSessionCookie(
      { name: "__Host-camera-ai-session", secure: true },
      value,
    );
    expect(header).toContain("Path=/; HttpOnly; SameSite=Strict; Secure");
    expect(header).not.toContain("Domain=");
    expect(header).not.toContain("Max-Age=");
    expect(header).not.toContain("Expires=");

    const cleared = serializeClearedSessionCookie({
      name: "__Host-camera-ai-session",
      secure: true,
    });
    expect(cleared).toContain("Max-Age=0");
    expect(cleared).not.toContain("Domain=");
  });

  it("compares only well-shaped CSRF values against the session digest", () => {
    const value = randomBytes(32).toString("base64url");
    const digest = (candidate: string) =>
      createHash("sha256").update(candidate).digest();
    expect(constantTimeCsrfMatch(value, digest(value), digest)).toBe(true);
    expect(constantTimeCsrfMatch(`${value}x`, digest(value), digest)).toBe(
      false,
    );
    expect(constantTimeCsrfMatch("short", digest(value), digest)).toBe(false);
  });
});
