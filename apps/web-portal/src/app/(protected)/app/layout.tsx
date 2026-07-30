import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { readSessionSnapshot } from "@/features/auth/application/session";
import { resolveRouteAccess } from "@/features/auth/domain/route-access";

export const dynamic = "force-dynamic";

export default async function ProtectedLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const session = await readSessionSnapshot();
  const decision = resolveRouteAccess({
    pathname: "/app",
    session,
  });

  if (decision.kind === "redirect") {
    redirect(`${decision.destination}?reason=${decision.reason}`);
  }

  return children;
}
