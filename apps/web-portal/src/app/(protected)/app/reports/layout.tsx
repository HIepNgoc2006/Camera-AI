import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { readSessionSnapshot } from "@/features/auth/application/session";
import {
  buildInternalRedirect,
  resolveRouteAccess,
} from "@/features/auth/domain/route-access";

export const dynamic = "force-dynamic";

export default async function ReportsLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const session = await readSessionSnapshot();
  const decision = resolveRouteAccess({
    pathname: "/app/reports",
    session,
  });

  if (decision.kind === "redirect") {
    redirect(buildInternalRedirect(decision));
  }

  return children;
}
