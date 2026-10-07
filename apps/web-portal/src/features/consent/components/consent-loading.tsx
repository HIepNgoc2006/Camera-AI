export function ConsentLoading() {
  return (
    <section
      className="consent-page"
      aria-labelledby="consent-loading-title"
      aria-busy="true"
      aria-live="polite"
    >
      <header className="consent-heading">
        <div>
          <p className="eyebrow">Quyền riêng tư</p>
          <h1 id="consent-loading-title">Đồng ý xử lý dữ liệu</h1>
        </div>
      </header>
      <div className="consent-loading">
        <strong>Đang tải trạng thái đồng ý…</strong>
        <span>Hệ thống đang xác minh phiên và phạm vi quyền riêng tư.</span>
      </div>
    </section>
  );
}
