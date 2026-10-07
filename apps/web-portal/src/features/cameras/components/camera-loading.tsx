export function CameraLoading() {
  return (
    <section
      className="camera-page"
      aria-labelledby="camera-loading-title"
      aria-busy="true"
      aria-live="polite"
    >
      <header className="camera-heading">
        <div>
          <p className="eyebrow">Vận hành</p>
          <h1 id="camera-loading-title">Trạng thái camera và ANSVIS</h1>
        </div>
      </header>
      <div className="camera-loading">
        <strong>Đang tải trạng thái camera…</strong>
        <span>Hệ thống đang xác minh phiên và phạm vi khu vực.</span>
      </div>
    </section>
  );
}
