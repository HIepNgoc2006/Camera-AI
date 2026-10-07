import type { AccessListViewState } from "@/features/access/application/query-access";
import type { AccessQuery } from "@/features/access/domain/access-view";

import { AccessResults } from "./access-results";

export function AccessView({
  state,
}: Readonly<{ state: AccessListViewState }>) {
  const query =
    state.kind === "success" ||
    state.kind === "empty" ||
    state.kind === "unavailable"
      ? state.query
      : { cursor: null, limit: 25 };

  return (
    <section className="access-page" aria-labelledby="access-title">
      <header className="access-heading">
        <div>
          <p className="eyebrow">Quản trị truy cập</p>
          <h1 id="access-title">Phân quyền người dùng</h1>
        </div>
        <p className="access-heading-copy">
          Xem các gán vai trò trong phạm vi trường đã phân quyền. Mọi thay đổi
          vai trò cần phê duyệt kép; tự phê duyệt cho chính mình bị chặn.
        </p>
      </header>

      {state.kind !== "denied" ? <AccessFilters query={query} /> : null}
      <AccessContent state={state} />
    </section>
  );
}

function AccessFilters({ query }: Readonly<{ query: AccessQuery }>) {
  return (
    <form
      className="access-filters"
      action="/app/access"
      method="get"
      aria-label="Bộ lọc phân quyền"
    >
      <label>
        Số dòng
        <input
          name="limit"
          type="number"
          min={1}
          max={100}
          defaultValue={query.limit}
        />
      </label>
      <button type="submit">Áp dụng</button>
    </form>
  );
}

function AccessContent({ state }: Readonly<{ state: AccessListViewState }>) {
  switch (state.kind) {
    case "validation":
      return (
        <AccessNotice
          tone="error"
          message="Tham số truy vấn không hợp lệ."
          code={state.errorCode}
        />
      );
    case "denied":
      return (
        <AccessNotice
          tone="error"
          message="Danh sách phân quyền không tồn tại hoặc bạn không có quyền xem."
          code="ACCESS_UNAVAILABLE"
        />
      );
    case "unavailable":
      return (
        <AccessNotice
          tone="warning"
          message="Dữ liệu phân quyền tạm thời chưa khả dụng."
          code="ACCESS_UNAVAILABLE"
        />
      );
    case "empty":
      return (
        <div className="access-empty" role="status" aria-live="polite">
          <h2>Không có gán vai trò phù hợp.</h2>
          <p>Chỉ các gán vai trò trong trường của bạn được hiển thị.</p>
        </div>
      );
    case "success":
      return <AccessResults state={state} />;
  }
}

function AccessNotice({
  tone,
  message,
  code,
}: Readonly<{
  tone: "error" | "warning";
  message: string;
  code: string;
}>) {
  return (
    <div
      className={`access-notice access-notice-${tone}`}
      role="status"
      aria-live="polite"
    >
      <h2>{message}</h2>
      <p>
        Mã trạng thái: <code>{code}</code>
      </p>
    </div>
  );
}
