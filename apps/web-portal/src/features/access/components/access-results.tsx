import Link from "next/link";

import type { AccessListViewState } from "@/features/access/application/query-access";
import type { AccessQuery } from "@/features/access/domain/access-view";

const STATE_LABELS: Readonly<Record<string, string>> = {
  active: "Đang hiệu lực",
  expired: "Hết hạn",
  revoked: "Đã thu hồi",
};

export function AccessResults({
  state,
}: Readonly<{
  state: Extract<AccessListViewState, { readonly kind: "success" }>;
}>) {
  return (
    <div className="access-results">
      <div className="access-table-wrap">
        <table className="access-table">
          <caption>Gán vai trò đã được phân quyền</caption>
          <thead>
            <tr>
              <th scope="col">Đối tượng</th>
              <th scope="col">Vai trò</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Hiệu lực</th>
              <th scope="col">Thay đổi</th>
            </tr>
          </thead>
          <tbody>
            {state.page.items.map((item) => (
              <tr key={item.assignmentId}>
                <th scope="row">{item.displayLabel}</th>
                <td>
                  <code>{item.roleCode}</code>
                </td>
                <td>
                  <span
                    className={`access-status access-status-${item.status}`}
                  >
                    {STATE_LABELS[item.status] ?? item.status}
                  </span>
                </td>
                <td>
                  <time dateTime={item.validFrom}>
                    {formatUtcInstant(item.validFrom)}
                  </time>
                  {item.validUntil ? (
                    <>
                      {" — "}
                      <time dateTime={item.validUntil}>
                        {formatUtcInstant(item.validUntil)}
                      </time>
                    </>
                  ) : null}
                </td>
                <td>
                  {state.canProposeChange && item.status === "active" ? (
                    <span className="access-mutation-note">
                      Đề xuất thay đổi cần phê duyệt kép và hợp đồng backend
                      đang hoạt động; hiện chưa khả dụng.
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
        <nav className="access-pagination" aria-label="Phân trang phân quyền">
          <Link href={buildNextPageHref(state.query, state.page.nextCursor)}>
            Trang tiếp theo
          </Link>
        </nav>
      ) : null}
    </div>
  );
}

function buildNextPageHref(query: AccessQuery, cursor: string): string {
  const search = new URLSearchParams({
    limit: String(query.limit),
    cursor,
  });
  return `/app/access?${search.toString()}`;
}

function formatUtcInstant(value: string): string {
  return `${value.slice(0, 10)} ${value.slice(11, 16)} UTC`;
}
