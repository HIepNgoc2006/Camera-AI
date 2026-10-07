export function ViolationLoading() {
  return (
    <section
      className="violation-page"
      aria-labelledby="violation-loading-title"
      aria-busy="true"
      aria-live="polite"
    >
      <header className="violation-heading">
        <div>
          <p className="eyebrow">Nghiệp vụ nhà trường</p>
          <h1 id="violation-loading-title">Nghi vấn — cần người xem xét</h1>
        </div>
      </header>
      <div className="violation-loading">
        <strong>Đang tải hồ sơ vi phạm…</strong>
        <span>Hệ thống đang xác minh phiên và phạm vi truy cập.</span>
      </div>
    </section>
  );
}
