import { handleLogoutRequest } from "@/features/auth/infrastructure/logout-route";

export async function POST(request: Request): Promise<Response> {
  return handleLogoutRequest(request, false);
}
