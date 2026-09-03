export function AttendanceLoading() {
  return (
    <section
      className="attendance-page"
      aria-labelledby="attendance-loading-title"
      aria-busy="true"
      aria-live="polite"
    >
      <header className="attendance-heading">
        <div>
          <p className="eyebrow">Nghiệp vụ nhà trường</p>
          <h1 id="attendance-loading-title">Điểm danh</h1>
        </div>
      </header>
      <div className="attendance-loading">
        <strong>Đang tải dữ liệu điểm danh…</strong>
        <span>Hệ thống đang xác minh phiên và phạm vi truy cập.</span>
      </div>
    </section>
  );
}
