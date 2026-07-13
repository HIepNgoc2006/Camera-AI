# Planning index - AI Camera School System

## Mục tiêu

Bộ planning này dùng để điều phối phát triển hệ thống AI Camera cho trường học theo hướng gọn, dễ đọc, nhưng vẫn đủ để triển khai nghiêm túc. Tài liệu ưu tiên bảo mật vì hệ thống xử lý dữ liệu trẻ em, khuôn mặt, ảnh/video sự kiện, điểm danh và chấm công.

## Nguồn sự thật hiện hành

- Kế hoạch điều phối kỹ thuật chính: [workstream-implementation-plan.md](workstream-implementation-plan.md).
- Phạm vi nghiệp vụ chính: sáu chức năng gồm điểm danh học sinh, chấm công giáo viên, xả rác, nghi vấn hút thuốc, đồng phục học sinh và PPE bếp.
- Capability AI/model hiện hành: [ansvis-model-capability-matrix.md](ansvis-model-capability-matrix.md).
- GitHub Issues là lớp theo dõi thực thi; không được tự mở rộng phạm vi khác với ba tài liệu trên.
- Happiness index là hạng mục tùy chọn/tương lai, không thuộc baseline triển khai hiện tại và không được chặn sáu chức năng chính.
- Các file trong `executive-summary/` dùng để trình bày; nếu có khác biệt, planning hiện hành và project requirements đã khóa phạm vi được ưu tiên.

## Cách đọc nhanh

| Nhu cầu | Đọc file |
|---|---|
| Xem hướng triển khai đã tách rõ Web/App, ANSVIS integration và AI training | [workstream-implementation-plan.md](workstream-implementation-plan.md) |
| Xem model ANSVIS đã có/chưa có và hướng xử lý từng chức năng | [ansvis-model-capability-matrix.md](ansvis-model-capability-matrix.md) |
| Xem toàn bộ kế hoạch và thứ tự triển khai | [system-master-plan.md](system-master-plan.md) |
| Xem kiến trúc microservices, database, tool, thư viện | [architecture-stack.md](architecture-stack.md) |
| Xem thiết kế PostgreSQL, mã hóa dữ liệu, backup, retention | [database-and-encryption-plan.md](database-and-encryption-plan.md) |
| Xem checklist công cụ/phần mềm/thư viện cần chuẩn bị | [tooling-requirements.md](tooling-requirements.md) |
| Xem checklist cài đặt trước khi xây dựng hệ thống | [setup-prerequisites-checklist.md](setup-prerequisites-checklist.md) |
| Xem bảo mật, privacy, `.env`, secret, consent | [security-privacy-plan.md](security-privacy-plan.md) |
| Xem AI, ANSVIS, ANSTS, chống thất thoát dữ liệu AI | [ai-ansvis-plan.md](ai-ansvis-plan.md) |
| Xem rules cho agent/developer, folder, design patterns | [coding-agent-rules.md](coding-agent-rules.md) và root [../../AGENTS.md](../../AGENTS.md) |
| Xem rules chống lan man/scope creep cho Agent | [agent-scope-control-rules.md](agent-scope-control-rules.md) |
| Xem QA, test, phase check, acceptance | [delivery-quality-plan.md](delivery-quality-plan.md) |
| Xem tracking tiến độ, bug, release, vận hành, log | [operations-tracking-plan.md](operations-tracking-plan.md) |
| Xem rủi ro rò rỉ dữ liệu, bảo mật, maintainability | [risk-assessment.md](risk-assessment.md) |
| Xem kết quả audit trước khi code | [pre-code-readiness-audit.md](pre-code-readiness-audit.md) |
| Xem đối chiếu yêu cầu - docs - GitHub issues | [requirements-issues-traceability-audit.md](requirements-issues-traceability-audit.md) |

## Quy tắc chính

- Security là gate bắt buộc ở mọi phase, không phải việc làm cuối.
- Không lưu dữ liệu thật của học sinh, ảnh mặt, video camera, face DB, license key hoặc `.env` thật vào Git.
- Không dùng dữ liệu sinh trắc học nếu chưa có consent hợp lệ.
- Không để service đọc chéo database của service khác.
- Không đưa AI event vào production nếu chưa qua shadow mode và human review rule.
- Không nghiệm thu nếu chưa có audit log, backup/restore evidence, vulnerability scan và rollback plan.
- Không code database/encryption nếu chưa đọc [database-and-encryption-plan.md](database-and-encryption-plan.md).
- Không thêm tài liệu/issue mới nếu không có gap thật; xem [agent-scope-control-rules.md](agent-scope-control-rules.md).
