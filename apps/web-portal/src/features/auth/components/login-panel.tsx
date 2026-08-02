"use client";

import { type FormEvent, useEffect, useState } from "react";

import { WEB_BFF_SESSION_POLICY_VERSION } from "@/features/auth/domain/route-access";

const PUBLIC_STATES = new Set([
  "unauthenticated",
  "mfa_required",
  "mfa_failed",
  "authenticated",
  "expired",
  "revoked",
  "unavailable",
  "malformed",
]);

const PUBLIC_ERROR_CODES = new Set([
  "AUTH_REQUIRED",
  "MFA_REQUIRED",
  "AUTH_FAILED",
  "AUTHENTICATED",
  "SESSION_UNAVAILABLE",
  "SESSION_INVALID",
  "REQUEST_REJECTED",
]);

type AuthView = Readonly<{
  status: string;
  errorCode: string;
  csrfToken?: string;
  redirectTo?: string;
}>;

export function LoginPanel() {
  const [view, setView] = useState<AuthView>({
    status: "unavailable",
    errorCode: "SESSION_UNAVAILABLE",
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let current = true;
    void loadAuthView()
      .then((next) => {
        if (!current) return;
        if (next.status === "authenticated" && next.redirectTo === "/app") {
          window.location.assign("/app");
          return;
        }
        setView(next);
      })
      .catch(() => {
        if (current) {
          setView({
            status: "unavailable",
            errorCode: "SESSION_UNAVAILABLE",
          });
        }
      });
    return () => {
      current = false;
    };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!view.csrfToken || submitting) return;
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    const mfaCode = String(form.get("mfaCode") ?? "");
    let requestBody = JSON.stringify({
      tenantId: String(form.get("tenantId") ?? ""),
      identifier: String(form.get("identifier") ?? ""),
      password: String(form.get("password") ?? ""),
      ...(mfaCode ? { mfaCode } : {}),
    });
    event.currentTarget.reset();
    try {
      const pendingResponse = fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": view.csrfToken,
        },
        body: requestBody,
      });
      requestBody = "";
      const response = await pendingResponse;
      const next = await parseAuthView(response);
      if (next.status === "authenticated" && next.redirectTo === "/app") {
        window.location.assign("/app");
        return;
      }
      const prepared = await loadAuthView();
      setView(
        next.errorCode === "AUTH_FAILED" || next.errorCode === "MFA_REQUIRED"
          ? { ...prepared, status: next.status, errorCode: next.errorCode }
          : prepared,
      );
    } catch {
      setView({ status: "unavailable", errorCode: "SESSION_UNAVAILABLE" });
    } finally {
      setSubmitting(false);
    }
  }

  const needsMfa =
    view.status === "mfa_required" || view.status === "mfa_failed";
  const canSubmit = Boolean(view.csrfToken) && !submitting;

  return (
    <section className="panel auth-panel" aria-labelledby="login-title">
      <p className="eyebrow">AI Camera School</p>
      <h1 id="login-title">Đăng nhập</h1>
      <AuthMessage view={view} />
      {view.status !== "unavailable" && view.status !== "malformed" ? (
        <form className="auth-form" onSubmit={submit}>
          <label>
            Mã đơn vị
            <input
              name="tenantId"
              type="text"
              inputMode="text"
              autoComplete="organization"
              required
              maxLength={36}
            />
          </label>
          <label>
            Tài khoản
            <input
              name="identifier"
              type="text"
              autoComplete="username"
              required
              maxLength={254}
            />
          </label>
          <label>
            Mật khẩu
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              maxLength={1024}
            />
          </label>
          {needsMfa ? (
            <label>
              Mã xác thực
              <input
                name="mfaCode"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                required
              />
            </label>
          ) : null}
          <button type="submit" disabled={!canSubmit}>
            {submitting ? "Đang xác thực…" : "Tiếp tục"}
          </button>
        </form>
      ) : null}
    </section>
  );
}

function AuthMessage({ view }: Readonly<{ view: AuthView }>) {
  if (view.errorCode === "MFA_REQUIRED") {
    return <p className="notice">Cần thêm bước xác thực để tiếp tục.</p>;
  }
  if (view.errorCode === "AUTH_FAILED") {
    return (
      <p className="notice error">Không thể xác thực. Vui lòng thử lại.</p>
    );
  }
  if (view.errorCode === "SESSION_INVALID") {
    return (
      <p className="notice error">
        Phiên không hợp lệ. Vui lòng tải lại trang.
      </p>
    );
  }
  if (view.errorCode === "SESSION_UNAVAILABLE") {
    return (
      <p className="notice error">
        Dịch vụ đăng nhập đang tạm thời không khả dụng. Vui lòng thử lại sau.
      </p>
    );
  }
  if (view.errorCode === "REQUEST_REJECTED") {
    return (
      <p className="notice error">
        Yêu cầu không hợp lệ. Vui lòng tải lại trang.
      </p>
    );
  }
  return <p className="muted">Nhập thông tin do nhà trường cấp.</p>;
}

async function loadAuthView(): Promise<AuthView> {
  const response = await fetch("/api/auth/session", {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
  });
  return parseAuthView(response);
}

async function parseAuthView(response: Response): Promise<AuthView> {
  const value: unknown = await response.json();
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value) ||
    (value as Record<string, unknown>).policyVersion !==
      WEB_BFF_SESSION_POLICY_VERSION ||
    typeof (value as Record<string, unknown>).status !== "string" ||
    !PUBLIC_STATES.has((value as Record<string, string>).status) ||
    typeof (value as Record<string, unknown>).errorCode !== "string" ||
    !PUBLIC_ERROR_CODES.has((value as Record<string, string>).errorCode) ||
    (typeof (value as Record<string, unknown>).csrfToken === "string" &&
      !/^[A-Za-z0-9_-]{43,128}$/.test(
        (value as Record<string, string>).csrfToken,
      ))
  ) {
    throw new Error("BFF_AUTH_RESPONSE_INVALID");
  }
  const record = value as Record<string, unknown>;
  return {
    status: record.status as string,
    errorCode: record.errorCode as string,
    ...(typeof record.csrfToken === "string"
      ? { csrfToken: record.csrfToken }
      : {}),
    ...(record.redirectTo === "/app" || record.redirectTo === "/login"
      ? { redirectTo: record.redirectTo }
      : {}),
  };
}
