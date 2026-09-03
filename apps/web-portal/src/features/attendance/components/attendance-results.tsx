import Link from "next/link";

import type { AttendanceViewState } from "@/features/attendance/application/query-attendance";
import type {
  AttendanceQuery,
  AttendanceRecord,
  AttendanceStatus,
} from "@/features/attendance/domain/attendance-view";

const STATUS_LABELS: Readonly<Record<AttendanceStatus, string>> = {
  present: "Có mặt",
  late: "Đi muộn",
  absent: "Vắng",
  pending_review: "Chờ duyệt",
};

export function AttendanceResults({
  state,
}: Readonly<{
  state: Extract<AttendanceViewState, { readonly kind: "success" }>;
}>) {
  const counts = countStatuses(state.page.records);

  return (
    <div className="attendance-results">
      <dl className="attendance-summary" aria-label="Tổng hợp trạng thái">
        {Object.entries(STATUS_LABELS).map(([status, label]) => (
          <div key={status} className={`attendance-summary-${status}`}>
            <dt>{label}</dt>
            <dd>{counts[status as AttendanceStatus]}</dd>
          </div>
        ))}
      </dl>

      <div className="attendance-table-wrap">
        <table className="attendance-table">
          <caption>Kết quả điểm danh đã được phân quyền</caption>
          <thead>
            <tr>
              <th scope="col">Học sinh</th>
              <th scope="col">Lớp</th>
              <th scope="col">Ngày</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Cập nhật</th>
              {state.canCorrect ? <th scope="col">Thao tác</th> : null}
            </tr>
          </thead>
          <tbody>
            {state.page.records.map((record) => (
              <AttendanceRow
                key={record.recordId}
                record={record}
                canCorrect={state.canCorrect}
              />
            ))}
          </tbody>
        </table>
      </div>

      {state.page.nextCursor ? (
        <nav
          className="attendance-pagination"
          aria-label="Phân trang điểm danh"
        >
          <Link href={buildNextPageHref(state.query, state.page.nextCursor)}>
            Trang tiếp theo
          </Link>
        </nav>
      ) : null}
    </div>
  );
}

function AttendanceRow({
  record,
  canCorrect,
}: Readonly<{ record: AttendanceRecord; canCorrect: boolean }>) {
  return (
    <tr>
      <th scope="row">{record.displayLabel}</th>
      <td>{record.classLabel}</td>
      <td>
        <time dateTime={record.day}>{formatDay(record.day)}</time>
      </td>
      <td>
        <span
          className={`attendance-status attendance-status-${record.status}`}
        >
          {STATUS_LABELS[record.status]}
        </span>
      </td>
      <td>
        <time dateTime={record.updatedAt}>
          {formatUtcInstant(record.updatedAt)}
        </time>
      </td>
      {canCorrect ? (
        <td>
          <details className="attendance-correction">
            <summary>Hiệu chỉnh</summary>
            <p>
              Yêu cầu hiệu chỉnh chỉ được gửi khi BFF xác nhận lại quyền, phạm
              vi, idempotency và audit.
            </p>
          </details>
        </td>
      ) : null}
    </tr>
  );
}

function countStatuses(
  records: readonly AttendanceRecord[],
): Record<AttendanceStatus, number> {
  const counts: Record<AttendanceStatus, number> = {
    present: 0,
    late: 0,
    absent: 0,
    pending_review: 0,
  };
  for (const record of records) {
    counts[record.status] += 1;
  }
  return counts;
}

function buildNextPageHref(query: AttendanceQuery, cursor: string): string {
  const search = new URLSearchParams({
    day: query.day,
    limit: String(query.limit),
    cursor,
  });
  if (query.classId) {
    search.set("classId", query.classId);
  }
  return `/app/attendance?${search.toString()}`;
}

function formatDay(day: string): string {
  const [year, month, date] = day.split("-");
  return `${date}/${month}/${year}`;
}

function formatUtcInstant(value: string): string {
  return `${value.slice(0, 10)} ${value.slice(11, 16)} UTC`;
}
