import { AppShell } from "@/features/shell/components/app-shell";

export default function ApplicationPage() {
  return (
    <AppShell>
      <section className="panel">
        <p className="eyebrow">Khung ứng dụng</p>
        <h1>Web Portal</h1>
        <p className="muted">
          Các màn hình nghiệp vụ sẽ được bổ sung theo từng issue sau khi hợp
          đồng xác thực và phân quyền được tích hợp.
        </p>
      </section>
    </AppShell>
  );
}
