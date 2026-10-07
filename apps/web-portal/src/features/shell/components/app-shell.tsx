import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({
  children,
  showAttendanceNavigation = false,
  showViolationNavigation = false,
  showReportNavigation = false,
}: Readonly<{
  children: ReactNode;
  showAttendanceNavigation?: boolean;
  showViolationNavigation?: boolean;
  showReportNavigation?: boolean;
}>) {
  const showNavigation =
    showAttendanceNavigation || showViolationNavigation || showReportNavigation;

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
              <Link href="/app/violations">Vi phạm</Link>
            ) : null}
            {showReportNavigation ? (
              <Link href="/app/reports" aria-current="page">
                Báo cáo
              </Link>
            ) : null}
          </nav>
        ) : null}
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
