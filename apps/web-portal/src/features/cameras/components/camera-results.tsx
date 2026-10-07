import Link from "next/link";

import type { CameraHealthListViewState } from "@/features/cameras/application/query-camera";
import { summarizeCameraHealth } from "@/features/cameras/application/query-camera";
import type {
  CameraHealthQuery,
  CameraHealthView,
} from "@/features/cameras/domain/camera-view";

const CONNECTIVITY_LABELS: Readonly<Record<string, string>> = {
  online: "Kết nối tốt",
  offline: "Mất kết nối",
  unknown: "Chưa xác định",
};

const TASK_LABELS: Readonly<Record<string, string>> = {
  running: "Task đang chạy",
  stopped: "Task đã dừng",
  unknown: "Chưa xác định",
};

const EVENT_DELAY_LABELS: Readonly<Record<string, string>> = {
  flowing: "Sự kiện đều",
  delayed: "Sự kiện trễ",
  no_recent_event: "Không có sự kiện gần đây",
  unknown: "Chưa xác định",
};

const COLLECTION_LABELS: Readonly<Record<string, string>> = {
  available: "Thu thập ổn định",
  unavailable: "Thu thập gián đoạn",
  unknown: "Chưa xác định",
};

export function CameraResults({
  state,
}: Readonly<{
  state: Extract<CameraHealthListViewState, { readonly kind: "success" }>;
}>) {
  return (
    <div className="camera-results">
      <p className="camera-updated">
        Dữ liệu lần gần nhất:{" "}
        <time dateTime={state.page.items[0]?.lastObservedAt ?? undefined}>
          {state.page.items[0]?.lastObservedAt
            ? formatUtcInstant(state.page.items[0].lastObservedAt)
            : "chưa có mẫu"}
        </time>
      </p>
      <div className="camera-table-wrap">
        <table className="camera-table">
          <caption>Trạng thái camera đã được phân quyền</caption>
          <thead>
            <tr>
              <th scope="col">Camera</th>
              <th scope="col">Kết nối</th>
              <th scope="col">Task ANSVIS</th>
              <th scope="col">Sự kiện</th>
              <th scope="col">Thu thập</th>
              <th scope="col">Chẩn đoán</th>
            </tr>
          </thead>
          <tbody>
            {state.page.items.map((item) => (
              <tr key={item.cameraId}>
                <th scope="row">
                  {item.displayLabel}
                  <span className="camera-zone">{item.zoneLabel}</span>
                </th>
                <td>
                  <span
                    className={`camera-state camera-state-${item.connectivity}`}
                  >
                    <span
                      className="camera-state-dot"
                      aria-hidden="true"
                    ></span>
                    {CONNECTIVITY_LABELS[item.connectivity] ??
                      item.connectivity}
                  </span>
                </td>
                <td>
                  <span className={`camera-task camera-task-${item.taskState}`}>
                    {TASK_LABELS[item.taskState] ?? item.taskState}
                  </span>
                </td>
                <td>
                  {EVENT_DELAY_LABELS[item.eventDelay] ?? item.eventDelay}
                </td>
                <td>{COLLECTION_LABELS[item.collection] ?? item.collection}</td>
                <td>
                  <CameraDiagnosisCell view={item} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {state.page.nextCursor ? (
        <nav className="camera-pagination" aria-label="Phân trang camera">
          <Link href={buildNextPageHref(state.query, state.page.nextCursor)}>
            Trang tiếp theo
          </Link>
        </nav>
      ) : null}
    </div>
  );
}

function CameraDiagnosisCell({ view }: Readonly<{ view: CameraHealthView }>) {
  const diagnosis = summarizeCameraHealth(view);
  return <span>{diagnosis.headline}</span>;
}

function buildNextPageHref(query: CameraHealthQuery, cursor: string): string {
  const search = new URLSearchParams({
    limit: String(query.limit),
    cursor,
  });
  return `/app/cameras?${search.toString()}`;
}

function formatUtcInstant(value: string): string {
  return `${value.slice(0, 10)} ${value.slice(11, 16)} UTC`;
}
