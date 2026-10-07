import type { ReportListViewState } from "@/features/reports/application/query-report";
import type { ReportQuery } from "@/features/reports/domain/report-view";

import { ReportResults } from "./report-results";

export function ReportView({
  state,
}: Readonly<{ state: ReportListViewState }>) {
  const query =
    state.kind === "success" ||
    state.kind === "empty" ||
    state.kind === "unavailable"
      ? state.query
      : { day: "", classId: null, cursor: null, limit: 25 };

  return (
    <section className="report-page" aria-labelledby="report-title">
      <header className="report-heading">
        <div>
          <p className="eyebrow">Nghiệp vụ nhà trường</p>
          <h1 id="report-title">Báo cáo tổng hợp</h1>
        </div>
        <p className="report-heading-copy">
          Tra cứu báo cáo đã được phân quyền theo ngày và lớp học. Dữ liệu dưới
          ngưỡng đoàn thể tối thiểu được ẩn để bảo vệ quyền riêng tư.
        </p>
      </header>

      {state.kind !== "denied" ? <ReportFilters query={query} /> : null}
      <ReportContent state={state} />
    </section>
  );
}

function ReportFilters({ query }: Readonly<{ query: ReportQuery }>) {
  return (
    <form
      className="report-filters"
      action="/app/reports"
      method="get"
      aria-label="Bộ lọc báo cáo"
    >
      <label>
        Ngày
        <input name="day" type="date" defaultValue={query.day} />
      </label>
      <label>
        Mã lớp
        <input
          name="classId"
          type="text"
          inputMode="text"
          maxLength={36}
          pattern="[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
          defaultValue={query.classId ?? ""}
          placeholder="UUID lớp được phân quyền"
        />
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

function ReportContent({ state }: Readonly<{ state: ReportListViewState }>) {
  switch (state.kind) {
    case "validation":
      return (
        <ReportNotice
          tone="error"
          message="Bộ lọc báo cáo không hợp lệ."
          code={state.errorCode}
        />
      );
    case "denied":
      return (
        <ReportNotice
          tone="error"
          message="Báo cáo không tồn tại hoặc bạn không có quyền xem."
          code="REPORT_UNAVAILABLE"
        />
      );
    case "unavailable":
      return (
        <ReportNotice
          tone="warning"
          message="Dữ liệu báo cáo tạm thời chưa khả dụng."
          code="REPORT_UNAVAILABLE"
        />
      );
    case "empty":
      return (
        <div className="report-empty" role="status" aria-live="polite">
          <h2>Không có báo cáo phù hợp.</h2>
          <p>
            Hãy kiểm tra lại ngày hoặc mã lớp trong phạm vi được phân quyền.
          </p>
        </div>
      );
    case "success":
      return <ReportResults state={state} />;
  }
}

function ReportNotice({
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
      className={`report-notice report-notice-${tone}`}
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
