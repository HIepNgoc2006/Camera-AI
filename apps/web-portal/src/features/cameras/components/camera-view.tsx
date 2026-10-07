import type { CameraHealthListViewState } from "@/features/cameras/application/query-camera";
import { summarizeCameraHealth } from "@/features/cameras/application/query-camera";
import type { CameraHealthQuery } from "@/features/cameras/domain/camera-view";

import { CameraResults } from "./camera-results";

export function CameraView({
  state,
}: Readonly<{ state: CameraHealthListViewState }>) {
  const query =
    state.kind === "success" ||
    state.kind === "empty" ||
    state.kind === "unavailable"
      ? state.query
      : { cursor: null, limit: 25 };

  return (
    <section className="camera-page" aria-labelledby="camera-title">
      <header className="camera-heading">
        <div>
          <p className="eyebrow">Vận hành</p>
          <h1 id="camera-title">Trạng thái camera và ANSVIS</h1>
        </div>
        <p className="camera-heading-copy">
          Theo dõi kết nối camera, task ANSVIS và độ trễ sự kiện theo khu vực
          được phân quyền. Màn hình chỉ đọc; không điều khiển camera hay đánh
          giá chất lượng AI.
        </p>
      </header>

      {state.kind !== "denied" ? <CameraFilters query={query} /> : null}
      <CameraContent state={state} />
    </section>
  );
}

function CameraFilters({ query }: Readonly<{ query: CameraHealthQuery }>) {
  return (
    <form
      className="camera-filters"
      action="/app/cameras"
      method="get"
      aria-label="Bộ lọc trạng thái camera"
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
      <button type="submit">Làm mới</button>
    </form>
  );
}

function CameraContent({
  state,
}: Readonly<{ state: CameraHealthListViewState }>) {
  switch (state.kind) {
    case "validation":
      return (
        <CameraNotice
          tone="error"
          message="Tham số truy vấn không hợp lệ."
          code={state.errorCode}
        />
      );
    case "denied":
      return (
        <CameraNotice
          tone="error"
          message="Trạng thái camera không tồn tại hoặc bạn không có quyền xem."
          code="CAMERA_UNAVAILABLE"
        />
      );
    case "unavailable":
      return (
        <CameraNotice
          tone="warning"
          message="Dữ liệu trạng thái tạm thời chưa khả dụng. Không thể kết luận mọi camera đang mất kết nối."
          code="CAMERA_UNAVAILABLE"
        />
      );
    case "empty":
      return (
        <div className="camera-empty" role="status" aria-live="polite">
          <h2>Không có camera nào trong phạm vi phân quyền.</h2>
          <p>Chỉ camera thuộc trường và khu vực được phân quyền hiển thị.</p>
        </div>
      );
    case "success":
      return <CameraResults state={state} />;
  }
}

export function CameraNotice({
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
      className={`camera-notice camera-notice-${tone}`}
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

export function CameraDiagnosis({
  view,
}: Readonly<{
  view: Parameters<typeof summarizeCameraHealth>[0];
}>) {
  const diagnosis = summarizeCameraHealth(view);
  return (
    <span className="camera-diagnosis">
      {diagnosis.headline}
      <span className="visually-hidden">
        (mã chẩn đoán: {diagnosis.reasonCode})
      </span>
    </span>
  );
}
