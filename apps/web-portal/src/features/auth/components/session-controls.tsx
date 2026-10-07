"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { WEB_BFF_SESSION_POLICY_VERSION } from "@/features/auth/domain/route-access";

type Challenge = Readonly<{ csrfToken: string }>;

export function SessionControls({
  warningInitially,
  warningStartsAt,
  expiresAt,
}: Readonly<{
  warningInitially: boolean;
  warningStartsAt: string | null;
  expiresAt: string | null;
}>) {
  const [warning, setWarning] = useState(warningInitially);
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!warningStartsAt || !expiresAt) return;
    const cancelWarning = scheduleAt(warningStartsAt, () => setWarning(true));
    const cancelExpiry = scheduleAt(expiresAt, () =>
      window.location.replace("/login"),
    );
    return () => {
      cancelWarning();
      cancelExpiry();
    };
  }, [expiresAt, warningStartsAt]);

  async function endSession(allDevices: boolean) {
    if (busy) return;
    setBusy(true);
    setUnavailable(false);
    try {
      const challenge = await loadChallenge();
      const response = await fetch(
        allDevices ? "/api/auth/logout-all" : "/api/auth/logout",
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-CSRF-Token": challenge.csrfToken },
        },
      );
      const body: unknown = await response.json();
      if (
        typeof body !== "object" ||
        body === null ||
        Array.isArray(body) ||
        (body as Record<string, unknown>).policyVersion !==
          WEB_BFF_SESSION_POLICY_VERSION ||
        (body as Record<string, unknown>).redirectTo !== "/login"
      ) {
        throw new Error("BFF_LOGOUT_RESPONSE_INVALID");
      }
      router.push("/login");
    } catch {
      setUnavailable(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="session-controls" aria-live="polite">
      {warning ? (
        <p className="notice warning">
          Phiên sắp hết hạn. Hãy hoàn tất công việc và đăng nhập lại khi cần.
        </p>
      ) : null}
      {unavailable ? (
        <p className="notice error">
          Chưa thể xác nhận đăng xuất ở máy chủ. Quyền truy cập cục bộ đã bị từ
          chối; vui lòng thử lại.
        </p>
      ) : null}
      <div className="session-actions">
        <button type="button" disabled={busy} onClick={() => endSession(false)}>
          Đăng xuất
        </button>
        <button type="button" disabled={busy} onClick={() => endSession(true)}>
          Đăng xuất mọi thiết bị
        </button>
      </div>
    </aside>
  );
}

function scheduleAt(instant: string, action: () => void): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const target = Date.parse(instant);
  const tick = () => {
    const remaining = target - Date.now();
    if (remaining <= 0) {
      action();
      return;
    }
    timer = setTimeout(tick, Math.min(remaining, 2_147_483_647));
  };
  tick();
  return () => clearTimeout(timer);
}

async function loadChallenge(): Promise<Challenge> {
  const response = await fetch("/api/auth/session", {
    credentials: "same-origin",
    cache: "no-store",
  });
  const value: unknown = await response.json();
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value) ||
    (value as Record<string, unknown>).policyVersion !==
      WEB_BFF_SESSION_POLICY_VERSION ||
    typeof (value as Record<string, unknown>).csrfToken !== "string" ||
    !/^[A-Za-z0-9_-]{43,128}$/.test((value as Record<string, string>).csrfToken)
  ) {
    throw new Error("BFF_CSRF_CHALLENGE_INVALID");
  }
  return { csrfToken: (value as Record<string, string>).csrfToken };
}
