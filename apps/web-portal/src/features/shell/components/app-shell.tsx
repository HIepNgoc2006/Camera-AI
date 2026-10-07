import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({
  children,
  showAttendanceNavigation = false,
  showViolationNavigation = false,
}: Readonly<{
  children: ReactNode;
  showAttendanceNavigation?: boolean;
  showViolationNavigation?: boolean;
}>) {
  const showNavigation = showAttendanceNavigation || showViolationNavigation;

  return (
    <div className="shell">
      <header className="shell-header">
        <strong>AI Camera School</strong>
        {showNavigation ? (
          <nav className="shell-nav" aria-label="Điều hướng ứng dụng">
            <Link href="/app">Tổng quan</Link>
            {showAttendanceNavigation ? (
              <Link href="/app/attendance">Điểm danh</Link>
            ) : null}
            {showViolationNavigation ? (
              <Link href="/app/violations" aria-current="page">
                Vi phạm
              </Link>
            ) : null}
          </nav>
        ) : null}
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
