import type { AttendanceViewState } from "@/features/attendance/application/query-attendance";
import type { AttendanceQuery } from "@/features/attendance/domain/attendance-view";

import { AttendanceResults } from "./attendance-results";

const EMPTY_FILTER: AttendanceQuery = {
  day: "",
  classId: null,
  cursor: null,
  limit: 25,
};

export function AttendanceView({
  state,
}: Readonly<{ state: AttendanceViewState }>) {
  const query = readQuery(state);

  return (
    <section className="attendance-page" aria-labelledby="attendance-title">
      <header className="attendance-heading">
        <div>
          <p className="eyebrow">Nghiệp vụ nhà trường</p>
          <h1 id="attendance-title">Điểm danh</h1>
        </div>
        <p className="attendance-heading-copy">
          Tra cứu dữ liệu đã được phân quyền theo ngày và lớp học.
        </p>
      </header>

      {state.kind !== "denied" ? <AttendanceFilters query={query} /> : null}
      <AttendanceContent state={state} />
    </section>
  );
}

function AttendanceFilters({ query }: Readonly<{ query: AttendanceQuery }>) {
  return (
    <form
      className="attendance-filters"
      action="/app/attendance"
      method="get"
      aria-label="Bộ lọc điểm danh"
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

function AttendanceContent({
  state,
}: Readonly<{ state: AttendanceViewState }>) {
  switch (state.kind) {
    case "validation":
      return (
        <AttendanceNotice
          tone="error"
          message="Bộ lọc điểm danh không hợp lệ."
          code={state.errorCode}
        />
      );
    case "denied":
      return (
        <AttendanceNotice
          tone="error"
          message="Bản ghi không tồn tại hoặc bạn không có quyền xem."
          code="ATTENDANCE_RECORD_UNAVAILABLE"
        />
      );
    case "unavailable":
      return (
        <AttendanceNotice
          tone="warning"
          message="Dữ liệu điểm danh tạm thời chưa khả dụng."
          code="ATTENDANCE_UNAVAILABLE"
        />
      );
    case "empty":
      return (
        <div className="attendance-empty" role="status" aria-live="polite">
          <h2>Không có bản ghi điểm danh phù hợp.</h2>
          <p>
            Hãy kiểm tra lại ngày hoặc mã lớp trong phạm vi được phân quyền.
          </p>
        </div>
      );
    case "success":
      return <AttendanceResults state={state} />;
  }
}

function AttendanceNotice({
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
      className={`attendance-notice attendance-notice-${tone}`}
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

function readQuery(state: AttendanceViewState): AttendanceQuery {
  return state.kind === "success" ||
    state.kind === "empty" ||
    state.kind === "unavailable"
    ? state.query
    : EMPTY_FILTER;
}
