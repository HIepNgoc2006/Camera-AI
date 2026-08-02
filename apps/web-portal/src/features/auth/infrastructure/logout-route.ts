import "server-only";

import {
  isExpectedUnsafeOrigin,
  readOpaqueSessionCookie,
} from "@/features/auth/domain/request-security";
import { authJsonResponse } from "@/features/auth/infrastructure/route-response";
import { getServerBffBoundary } from "@/features/auth/infrastructure/server-boundary";

export async function handleLogoutRequest(
  request: Request,
  allDevices: boolean,
): Promise<Response> {
  const boundary = getServerBffBoundary();
  const cookieValue = boundary.cookieProfile
    ? readOpaqueSessionCookie(
        request.headers.get("cookie"),
        boundary.cookieProfile.name,
      )
    : null;
  const result = await boundary.service.logout({
    cookieValue,
    csrfToken: request.headers.get("x-csrf-token"),
    originAccepted: isExpectedUnsafeOrigin(
      request.headers.get("origin"),
      boundary.expectedOrigin,
    ),
    allDevices,
  });
  return authJsonResponse(result, boundary.cookieProfile, "/login");
}
