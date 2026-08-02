import {
  isExpectedUnsafeOrigin,
  readOpaqueSessionCookie,
} from "@/features/auth/domain/request-security";
import {
  authJsonResponse,
  readBoundedJson,
} from "@/features/auth/infrastructure/route-response";
import { getServerBffBoundary } from "@/features/auth/infrastructure/server-boundary";

export async function POST(request: Request): Promise<Response> {
  const boundary = getServerBffBoundary();
  const cookieValue = boundary.cookieProfile
    ? readOpaqueSessionCookie(
        request.headers.get("cookie"),
        boundary.cookieProfile.name,
      )
    : null;
  const result = await boundary.service.login({
    cookieValue,
    csrfToken: request.headers.get("x-csrf-token"),
    originAccepted: isExpectedUnsafeOrigin(
      request.headers.get("origin"),
      boundary.expectedOrigin,
    ),
    credentials: await readBoundedJson(request),
  });
  return authJsonResponse(result, boundary.cookieProfile, "/app");
}
