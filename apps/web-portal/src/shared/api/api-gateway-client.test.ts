import { describe, expect, it, vi } from "vitest";

import {
  ApiGatewayConfigurationError,
  ApiGatewayResponseError,
  createApiGatewayClient,
  parseApiGatewayBaseUrl,
} from "./api-gateway-client";

function fakeCredentialBearingUrl(): string {
  const url = new URL("https://gateway.example.invalid");
  url.username = "fake-user";
  url.password = "fake-password";
  return url.toString();
}

describe("parseApiGatewayBaseUrl", () => {
  it.each([
    undefined,
    "",
    "api-gateway.invalid",
    " http://127.0.0.1:8000",
    "http://gateway.example.invalid",
    fakeCredentialBearingUrl(),
    "https://gateway.example.invalid?token=secret",
  ])("rejects missing or unsafe configuration", (value) => {
    expect(() => parseApiGatewayBaseUrl(value)).toThrow(
      ApiGatewayConfigurationError,
    );
  });

  it("does not include the rejected value in the error", () => {
    const sensitiveValue = fakeCredentialBearingUrl();

    expect(() => parseApiGatewayBaseUrl(sensitiveValue)).toThrow(
      "API Gateway configuration is missing or invalid.",
    );

    try {
      parseApiGatewayBaseUrl(sensitiveValue);
    } catch (error) {
      expect(String(error)).not.toContain(sensitiveValue);
    }
  });

  it.each([
    "https://gateway.example.invalid",
    "http://localhost:8000",
    "http://127.0.0.1:8000/api/",
  ])("accepts an approved gateway base URL: %s", (value) => {
    expect(parseApiGatewayBaseUrl(value)).toBeInstanceOf(URL);
  });
});

describe("createApiGatewayClient", () => {
  it("uses the configured gateway and injected transport", async () => {
    const fakeFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createApiGatewayClient(
      "https://gateway.example.invalid/api/",
      fakeFetch,
    );

    await expect(
      client.request<{ status: string }>("/health"),
    ).resolves.toEqual({
      status: "ok",
    });
    expect(fakeFetch).toHaveBeenCalledOnce();
    expect(String(fakeFetch.mock.calls[0]?.[0])).toBe(
      "https://gateway.example.invalid/api/health",
    );
  });

  it("rejects absolute paths that could bypass the gateway", async () => {
    const client = createApiGatewayClient(
      "https://gateway.example.invalid/",
      vi.fn<typeof fetch>(),
    );

    await expect(
      client.request("//internal-service.invalid"),
    ).rejects.toBeInstanceOf(ApiGatewayConfigurationError);
  });

  it("returns a stable error without exposing a response body", async () => {
    const client = createApiGatewayClient(
      "https://gateway.example.invalid/",
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          new Response("sensitive upstream detail", { status: 403 }),
        ),
    );

    await expect(client.request("/events")).rejects.toEqual(
      new ApiGatewayResponseError(403),
    );
  });

  it("retains only a validated stable upstream error code", async () => {
    const client = createApiGatewayClient(
      "https://gateway.example.invalid/",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({
            error_code: "AUTH_MFA_REQUIRED",
            message: "detail that must not be exposed",
            request_id: "synthetic-request",
          }),
          {
            status: 401,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    await expect(client.request("/auth/login")).rejects.toEqual(
      new ApiGatewayResponseError(401, "AUTH_MFA_REQUIRED"),
    );
  });
});
