export function AccessLoading() {
  return (
    <section
      className="access-page"
      aria-labelledby="access-loading-title"
      aria-busy="true"
      aria-live="polite"
    >
      <header className="access-heading">
        <div>
          <p className="eyebrow">Quản trị truy cập</p>
          <h1 id="access-loading-title">Phân quyền người dùng</h1>
        </div>
      </header>
      <div className="access-loading">
        <strong>Đang tải phân quyền…</strong>
        <span>Hệ thống đang xác minh phiên, MFA và phạm vi truy cập.</span>
      </div>
    </section>
  );
}
