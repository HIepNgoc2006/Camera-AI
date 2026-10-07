import Link from "next/link";

import type { ViolationListViewState } from "@/features/violations/application/query-violation";
import type {
  ViolationCaseStatus,
  ViolationListItem,
  ViolationLegalHoldState,
  ViolationQuery,
} from "@/features/violations/domain/violation-view";

const STATUS_LABELS: Readonly<Record<ViolationCaseStatus, string>> = {
  suspected: "Nghi vấn — chờ người xem xét",
  pending_review: "Chờ xem xét",
  needs_evidence: "Cần bổ sung bằng chứng",
  confirmed: "Đã xác nhận",
  rejected: "Đã loại bỏ (dương tính giả)",
  closed: "Đã đóng",
};

const LEGAL_HOLD_LABELS: Readonly<Record<ViolationLegalHoldState, string>> = {
  none: "Không có tạm dừng lưu trữ",
  active: "Tạm dừng lưu trữ theo yêu cầu pháp lý",
  released: "Đã gỡ tạm dừng lưu trữ",
  unavailable: "Trạng thái lưu trữ chưa xác định",
};

export function ViolationResults({
  state,
}: Readonly<{
  state: Extract<ViolationListViewState, { readonly kind: "success" }>;
}>) {
  return (
    <div className="violation-results">
      <p className="violation-ai-note" role="note">
        Các cảnh báo dưới đây do hệ thống AI ghi nhận và chỉ mang tính nghi vấn.
        Người xem xét mới là người kết luận, kể cả trường hợp loại bỏ dương tính
        giả.
      </p>

      <div className="violation-table-wrap">
        <table className="violation-table">
          <caption>Hồ sơ vi phạm đã được phân quyền</caption>
          <thead>
            <tr>
              <th scope="col">Mã hồ sơ</th>
              <th scope="col">Loại cảnh báo</th>
              <th scope="col">Thời gian</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Tạm dừng lưu trữ</th>
              <th scope="col">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {state.page.items.map((item) => (
              <ViolationRow
                key={item.caseId}
                item={item}
                canReview={state.actions.canReview}
                canExport={state.actions.canExport}
              />
            ))}
          </tbody>
        </table>
      </div>

      {state.page.nextCursor ? (
        <nav className="violation-pagination" aria-label="Phân trang vi phạm">
          <Link href={buildNextPageHref(state.query, state.page.nextCursor)}>
            Trang tiếp theo
          </Link>
        </nav>
      ) : null}
    </div>
  );
}

function ViolationRow({
  item,
  canReview,
  canExport,
}: Readonly<{
  item: ViolationListItem;
  canReview: boolean;
  canExport: boolean;
}>) {
  return (
    <tr>
      <th scope="row">{item.caseRef}</th>
      <td>{CATEGORY_FALLBACK}</td>
      <td>
        <time dateTime={item.occurredAt}>
          {formatUtcInstant(item.occurredAt)}
        </time>
      </td>
      <td>
        <span
          className={`violation-status violation-status-${item.reviewStatus}`}
        >
          {STATUS_LABELS[item.reviewStatus]}
        </span>
        {item.appealState === "appealed" ? (
          <span className="violation-overlay">
            Đã có yêu cầu phản hồi (appeal)
          </span>
        ) : null}
        {item.correctionState === "corrected" ? (
          <span className="violation-overlay">Đã có hiệu chỉnh</span>
        ) : null}
      </td>
      <td>
        <span
          className={`violation-hold violation-hold-${item.legalHoldState}`}
        >
          {LEGAL_HOLD_LABELS[item.legalHoldState]}
        </span>
      </td>
      <td>
        {canReview ? (
          <details className="violation-action">
            <summary>Xem xét</summary>
            <p>
              Yêu cầu xem xét chỉ được gửi khi BFF xác nhận lại quyền, phạm vi
              và audit; AI không tự kết luận.
            </p>
          </details>
        ) : null}
        {canExport ? (
          <details className="violation-action">
            <summary>Xuất báo cáo</summary>
            <p>
              Xuất dữ liệu cần quyền riêng và hợp đồng backend đang hoạt động;
              hiện chưa khả dụng.
            </p>
          </details>
        ) : null}
        {!canReview && !canExport ? "—" : null}
      </td>
    </tr>
  );
}

const CATEGORY_FALLBACK = "Cảnh báo AI";

function buildNextPageHref(query: ViolationQuery, cursor: string): string {
  const search = new URLSearchParams({
    occurredFrom: query.occurredFrom,
    occurredTo: query.occurredTo,
    limit: String(query.limit),
    cursor,
  });
  if (query.status) {
    search.set("status", query.status);
  }
  return `/app/violations?${search.toString()}`;
}

function formatUtcInstant(value: string): string {
  return `${value.slice(0, 10)} ${value.slice(11, 16)} UTC`;
}
