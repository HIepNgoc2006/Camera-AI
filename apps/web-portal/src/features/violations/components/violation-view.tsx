import type { ViolationListViewState } from "@/features/violations/application/query-violation";
import type { ViolationQuery } from "@/features/violations/domain/violation-view";

import { ViolationResults } from "./violation-results";

const EMPTY_FILTER: ViolationQuery = {
  occurredFrom: "",
  occurredTo: "",
  status: null,
  cursor: null,
  limit: 25,
};

export function ViolationView({
  state,
}: Readonly<{ state: ViolationListViewState }>) {
  const query = readQuery(state);

  return (
    <section className="violation-page" aria-labelledby="violation-title">
      <header className="violation-heading">
        <div>
          <p className="eyebrow">Nghiệp vụ nhà trường</p>
          <h1 id="violation-title">Nghi vấn — cần người xem xét</h1>
        </div>
        <p className="violation-heading-copy">
          Danh sách cảnh báo do hệ thống AI ghi nhận, chờ người có thẩm quyền
          xem xét. Kết luận kỷ luật chỉ được đưa ra sau xác nhận của người xem
          xét.
        </p>
      </header>

      {state.kind !== "denied" ? <ViolationFilters query={query} /> : null}
      <ViolationContent state={state} />
    </section>
  );
}

function ViolationFilters({ query }: Readonly<{ query: ViolationQuery }>) {
  return (
    <form
      className="violation-filters"
      action="/app/violations"
      method="get"
      aria-label="Bộ lọc vi phạm"
    >
      <label>
        Từ ngày
        <input
          name="occurredFrom"
          type="date"
          defaultValue={query.occurredFrom}
        />
      </label>
      <label>
        Đến ngày
        <input name="occurredTo" type="date" defaultValue={query.occurredTo} />
      </label>
      <label>
        Trạng thái
        <select name="status" defaultValue={query.status ?? ""}>
          <option value="">Tất cả</option>
          <option value="suspected">Nghi vấn</option>
          <option value="pending_review">Chờ xem xét</option>
          <option value="needs_evidence">Cần bổ sung bằng chứng</option>
          <option value="confirmed">Đã xác nhận</option>
          <option value="rejected">Đã loại bỏ (dương tính giả)</option>
          <option value="closed">Đã đóng</option>
        </select>
      </label>
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

function ViolationContent({
  state,
}: Readonly<{ state: ViolationListViewState }>) {
  switch (state.kind) {
    case "validation":
      return (
        <ViolationNotice
          tone="error"
          message="Bộ lọc vi phạm không hợp lệ."
          code={state.errorCode}
        />
      );
    case "denied":
      return (
        <ViolationNotice
          tone="error"
          message="Hồ sơ không tồn tại hoặc bạn không có quyền xem."
          code="VIOLATION_CASE_UNAVAILABLE"
        />
      );
    case "unavailable":
      return (
        <ViolationNotice
          tone="warning"
          message="Dữ liệu vi phạm tạm thời chưa khả dụng."
          code="VIOLATION_UNAVAILABLE"
        />
      );
    case "empty":
      return (
        <div className="violation-empty" role="status" aria-live="polite">
          <h2>Không có hồ sơ vi phạm phù hợp.</h2>
          <p>
            Hãy kiểm tra lại khoảng thời gian hoặc trạng thái trong phạm vi được
            phân quyền.
          </p>
        </div>
      );
    case "success":
      return <ViolationResults state={state} />;
  }
}

function ViolationNotice({
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
      className={`violation-notice violation-notice-${tone}`}
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

function readQuery(state: ViolationListViewState): ViolationQuery {
  return state.kind === "success" ||
    state.kind === "empty" ||
    state.kind === "unavailable"
    ? state.query
    : EMPTY_FILTER;
}
