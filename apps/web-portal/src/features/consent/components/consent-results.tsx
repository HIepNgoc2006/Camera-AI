import Link from "next/link";

import type { ConsentListViewState } from "@/features/consent/application/query-consent";
import type { ConsentQuery } from "@/features/consent/domain/consent-view";

const CONSENT_STATE_LABELS: Readonly<Record<string, string>> = {
  pending: "Chờ xác nhận",
  granted: "Đã đồng ý",
  denied: "Đã từ chối",
  withdrawn: "Đã thu hồi",
  restricted: "Bị hạn chế",
  expired: "Hết hạn",
};

const WITHDRAWAL_STATE_LABELS: Readonly<Record<string, string>> = {
  requested: "Yêu cầu thu hồi đã ghi nhận",
  identity_verified: "Đã xác minh danh tính",
  effective: "Thu hồi có hiệu lực — chặn xử lý mới",
  propagating: "Đang truyền xóa tới hệ thống liên quan",
  partially_completed: "Hoàn thành một phần",
  completed: "Hoàn tất theo tiến trình",
  rejected: "Yêu cầu thu hồi bị từ chối",
  superseded: "Đã thay thế bằng bản ghi khác",
};

export function ConsentResults({
  state,
}: Readonly<{
  state: Extract<ConsentListViewState, { readonly kind: "success" }>;
}>) {
  return (
    <div className="consent-results">
      <div className="consent-table-wrap">
        <table className="consent-table">
          <caption>Bản ghi đồng ý đã được phân quyền</caption>
          <thead>
            <tr>
              <th scope="col">Bản ghi</th>
              <th scope="col">Mục đích</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Hiệu lực</th>
              <th scope="col">Thay đổi</th>
            </tr>
          </thead>
          <tbody>
            {state.page.items.map((item) => (
              <tr key={item.consentId}>
                <th scope="row">{item.displayLabel}</th>
                <td>
                  <code>{item.purposeCode}</code>
                </td>
                <td>
                  <span
                    className={`consent-status consent-status-${item.status}`}
                  >
                    {CONSENT_STATE_LABELS[item.status] ?? item.status}
                  </span>
                  {item.withdrawalState ? (
                    <p className="consent-withdrawal-note">
                      {WITHDRAWAL_STATE_LABELS[item.withdrawalState] ??
                        item.withdrawalState}
                    </p>
                  ) : null}
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
                  {state.canRecordDecision && item.status === "granted" ? (
                    <span className="consent-mutation-note">
                      Ghi nhận quyết định cần quyền `consent.correct` và hợp
                      đồng backend đang hoạt động; hiện chưa khả dụng. Thu hồi
                      phải đi qua quy trình riêng chưa được cấp quyền trên Web.
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
        <nav className="consent-pagination" aria-label="Phân trang đồng ý">
          <Link href={buildNextPageHref(state.query, state.page.nextCursor)}>
            Trang tiếp theo
          </Link>
        </nav>
      ) : null}
    </div>
  );
}

function buildNextPageHref(query: ConsentQuery, cursor: string): string {
  const search = new URLSearchParams({
    limit: String(query.limit),
    cursor,
  });
  return `/app/consent?${search.toString()}`;
}

function formatUtcInstant(value: string): string {
  return `${value.slice(0, 10)} ${value.slice(11, 16)} UTC`;
}
