import { readOpaqueSessionCookie } from "@/features/auth/domain/request-security";
import { authJsonResponse } from "@/features/auth/infrastructure/route-response";
import { getServerBffBoundary } from "@/features/auth/infrastructure/server-boundary";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  const boundary = getServerBffBoundary();
  const cookieValue = boundary.cookieProfile
    ? readOpaqueSessionCookie(
        request.headers.get("cookie"),
        boundary.cookieProfile.name,
      )
    : null;
  return authJsonResponse(
    await boundary.service.prepare(cookieValue),
    boundary.cookieProfile,
  );
}
