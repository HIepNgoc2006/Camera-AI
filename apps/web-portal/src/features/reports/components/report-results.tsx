import Link from "next/link";

import type { ReportListViewState } from "@/features/reports/application/query-report";
import type { ReportQuery } from "@/features/reports/domain/report-view";

export function ReportResults({
  state,
}: Readonly<{
  state: Extract<ReportListViewState, { readonly kind: "success" }>;
}>) {
  return (
    <div className="report-results">
      <div className="report-table-wrap">
        <table className="report-table">
          <caption>Báo cáo đã được phân quyền</caption>
          <thead>
            <tr>
              <th scope="col">Báo cáo</th>
              <th scope="col">Ngày</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Cập nhật</th>
              <th scope="col">Xuất dữ liệu</th>
            </tr>
          </thead>
          <tbody>
            {state.page.items.map((item) => (
              <tr key={item.reportId}>
                <th scope="row">{item.displayLabel}</th>
                <td>
                  <time dateTime={item.day}>{formatDay(item.day)}</time>
                </td>
                <td>
                  <span
                    className={`report-status report-status-${item.status}`}
                  >
                    {item.status === "available" ? "Khả dụng" : item.status}
                  </span>
                </td>
                <td>
                  <time dateTime={item.updatedAt}>
                    {formatUtcInstant(item.updatedAt)}
                  </time>
                </td>
                <td>
                  {state.canExport ? (
                    <span className="report-export-note">
                      Xuất dữ liệu cần phê duyệt kép và hợp đồng backend đang
                      hoạt động; hiện chưa khả dụng.
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {state.page.nextCursor ? (
        <nav className="report-pagination" aria-label="Phân trang báo cáo">
          <Link href={buildNextPageHref(state.query, state.page.nextCursor)}>
            Trang tiếp theo
          </Link>
        </nav>
      ) : null}
    </div>
  );
}

function buildNextPageHref(query: ReportQuery, cursor: string): string {
  const search = new URLSearchParams({
    day: query.day,
    limit: String(query.limit),
    cursor,
  });
  if (query.classId) {
    search.set("classId", query.classId);
  }
  return `/app/reports?${search.toString()}`;
}

function formatDay(day: string): string {
  const [year, month, date] = day.split("-");
  return `${date}/${month}/${year}`;
}

function formatUtcInstant(value: string): string {
  return `${value.slice(0, 10)} ${value.slice(11, 16)} UTC`;
}
