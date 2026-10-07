import type { ConsentListViewState } from "@/features/consent/application/query-consent";
import type { ConsentQuery } from "@/features/consent/domain/consent-view";

import { ConsentResults } from "./consent-results";

export function ConsentView({
  state,
}: Readonly<{ state: ConsentListViewState }>) {
  const query =
    state.kind === "success" ||
    state.kind === "empty" ||
    state.kind === "unavailable"
      ? state.query
      : { cursor: null, limit: 25 };

  return (
    <section className="consent-page" aria-labelledby="consent-title">
      <header className="consent-heading">
        <div>
          <p className="eyebrow">Quyền riêng tư</p>
          <h1 id="consent-title">Đồng ý xử lý dữ liệu</h1>
        </div>
        <p className="consent-heading-copy">
          Tra cứu trạng thái đồng ý theo từng mục đích xử lý. Thu hồi đồng ý
          chặn xử lý mới ngay lập tức, nhưng dữ liệu cũ chỉ được xử lý theo tiến
          trình sau đó — không phải xóa ngay lập tức.
        </p>
      </header>

      {state.kind !== "denied" ? <ConsentFilters query={query} /> : null}
      <ConsentContent state={state} />
    </section>
  );
}

function ConsentFilters({ query }: Readonly<{ query: ConsentQuery }>) {
  return (
    <form
      className="consent-filters"
      action="/app/consent"
      method="get"
      aria-label="Bộ lọc đồng ý"
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

function ConsentContent({ state }: Readonly<{ state: ConsentListViewState }>) {
  switch (state.kind) {
    case "validation":
      return (
        <ConsentNotice
          tone="error"
          message="Tham số truy vấn không hợp lệ."
          code={state.errorCode}
        />
      );
    case "denied":
      return (
        <ConsentNotice
          tone="error"
          message="Danh sách đồng ý không tồn tại hoặc bạn không có quyền xem."
          code="CONSENT_UNAVAILABLE"
        />
      );
    case "unavailable":
      return (
        <ConsentNotice
          tone="warning"
          message="Dữ liệu đồng ý tạm thời chưa khả dụng."
          code="CONSENT_UNAVAILABLE"
        />
      );
    case "empty":
      return (
        <div className="consent-empty" role="status" aria-live="polite">
          <h2>Không có bản ghi đồng ý phù hợp.</h2>
          <p>
            Chỉ các bản ghi trong phạm vi quyền được phân và liên hệ đã được xác
            minh mới hiển thị.
          </p>
        </div>
      );
    case "success":
      return <ConsentResults state={state} />;
  }
}

function ConsentNotice({
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
      className={`consent-notice consent-notice-${tone}`}
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
