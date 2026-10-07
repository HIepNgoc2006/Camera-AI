export function ReportLoading() {
  return (
    <section
      className="report-page"
      aria-labelledby="report-loading-title"
      aria-busy="true"
      aria-live="polite"
    >
      <header className="report-heading">
        <div>
          <p className="eyebrow">Nghiệp vụ nhà trường</p>
          <h1 id="report-loading-title">Báo cáo tổng hợp</h1>
        </div>
      </header>
      <div className="report-loading">
        <strong>Đang tải báo cáo…</strong>
        <span>Hệ thống đang xác minh phiên và phạm vi truy cập.</span>
      </div>
    </section>
  );
}
