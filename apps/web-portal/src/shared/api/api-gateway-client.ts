const CONFIGURATION_ERROR_MESSAGE =
  "API Gateway configuration is missing or invalid.";

export class ApiGatewayConfigurationError extends Error {
  readonly code = "API_GATEWAY_CONFIGURATION_INVALID";

  constructor() {
    super(CONFIGURATION_ERROR_MESSAGE);
    this.name = "ApiGatewayConfigurationError";
  }
}

export class ApiGatewayResponseError extends Error {
  readonly code = "API_GATEWAY_RESPONSE_ERROR";

  constructor(
    readonly status: number,
    readonly upstreamErrorCode: string | null = null,
  ) {
    super("API Gateway request failed.");
    this.name = "ApiGatewayResponseError";
  }
}

export interface ApiGatewayClient {
  request<TResponse>(
    path: `/${string}`,
    init?: RequestInit,
  ): Promise<TResponse>;
}

function configurationError(): ApiGatewayConfigurationError {
  return new ApiGatewayConfigurationError();
}

function isLoopbackHost(hostname: string): boolean {
  return (
    hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]"
  );
}

export function parseApiGatewayBaseUrl(value: string | undefined): URL {
  if (!value || value.trim() !== value) {
    throw configurationError();
  }

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw configurationError();
  }

  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    (parsed.protocol === "http:" && !isLoopbackHost(parsed.hostname))
  ) {
    throw configurationError();
  }

  if (!parsed.pathname.endsWith("/")) {
    parsed.pathname = `${parsed.pathname}/`;
  }

  return parsed;
}

function buildGatewayUrl(baseUrl: URL, path: `/${string}`): URL {
  if (path.startsWith("//") || path.includes("\\") || URL.canParse(path)) {
    throw configurationError();
  }

  return new URL(path.slice(1), baseUrl);
}

export function createApiGatewayClient(
  configuredBaseUrl: string | undefined,
  fetchImplementation: typeof fetch = fetch,
): ApiGatewayClient {
  const baseUrl = parseApiGatewayBaseUrl(configuredBaseUrl);

  return {
    async request<TResponse>(
      path: `/${string}`,
      init: RequestInit = {},
    ): Promise<TResponse> {
      const response = await fetchImplementation(
        buildGatewayUrl(baseUrl, path),
        {
          ...init,
          headers: {
            Accept: "application/json",
            ...init.headers,
          },
        },
      );

      if (!response.ok) {
        throw new ApiGatewayResponseError(
          response.status,
          await readStableErrorCode(response),
        );
      }

      return (await response.json()) as TResponse;
    },
  };
}

async function readStableErrorCode(response: Response): Promise<string | null> {
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("application/json")) {
    return null;
  }
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      !Array.isArray(body) &&
      typeof (body as Record<string, unknown>).error_code === "string" &&
      /^[A-Z][A-Z0-9_]{2,63}$/.test(
        (body as Record<string, unknown>).error_code as string,
      )
    ) {
      return (body as Record<string, string>).error_code;
    }
  } catch {
    // Error bodies are never surfaced or logged.
  }
  return null;
}
