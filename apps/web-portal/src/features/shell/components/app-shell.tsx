import type { ReactNode } from "react";

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="shell">
      <header className="shell-header">
        <strong>AI Camera School</strong>
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
