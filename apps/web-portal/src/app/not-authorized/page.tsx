import Link from "next/link";

export default function NotAuthorizedPage() {
  return (
    <main className="centered-page">
      <section className="panel" aria-labelledby="not-authorized-title">
        <p className="eyebrow">Truy cập bị từ chối</p>
        <h1 id="not-authorized-title">Bạn không có quyền xem trang này</h1>
        <p className="muted">
          Quyền truy cập phải được xác nhận bởi API Gateway và dịch vụ backend.
        </p>
        <Link href="/login">Quay lại trang đăng nhập</Link>
      </section>
    </main>
  );
}
