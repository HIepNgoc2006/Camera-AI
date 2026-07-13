# KẾ HOẠCH TRIỂN KHAI PHẦN MỀM HỆ THỐNG AI CAMERA TRƯỜNG HỌC

**Phiên bản:** 1.0

**Trạng thái:** Dự thảo gửi khách hàng xem xét

**Ngày lập:** 07/07/2026

**Ngày khởi động dự án:** Chưa xác định

**Cách thể hiện tiến độ:** Tuần tương đối tính từ ngày khởi động chính thức (T0)
**Nguồn lực thực hiện:** 01 developer full-stack/AI/mobile, thực hiện tuần tự

## 0. Phạm vi, giả định và nguyên tắc lập kế hoạch

### 0.1 Phạm vi phần mềm

Hệ thống phục vụ 34 camera AI, gồm 16 camera điểm danh/đánh giá, 8 camera phát hiện xả rác, 8 camera phát hiện hút thuốc và 2 camera giám sát đồng phục/bảo hộ bếp ăn. Phạm vi phần mềm gồm backend, cơ sở dữ liệu, xử lý AI, Web Portal, ứng dụng React Native dùng chung mã nguồn cho iOS/Android, tích hợp luồng camera/API, bảo mật, kiểm thử, triển khai và tài liệu vận hành.

Không thuộc phạm vi của developer: khảo sát hiện trường; lựa chọn, mua sắm hoặc lắp camera/NVR/máy chủ; kéo dây, cấp nguồn, cấu hình mạng vật lý; bảo trì phần cứng. Khách hàng hoặc đơn vị thi công bàn giao luồng RTSP/ONVIF hoặc API, tài khoản kết nối, thông tin mạng và môi trường máy chủ đủ điều kiện.

### 0.2 Định hướng tích hợp ANSCENTER

Theo tài liệu do khách hàng cung cấp:

- [ANSVIS](https://doc.anscenter.com.au/docs/ANSVIS/Introduction/) là nền tảng phân tích video AI chạy trong mạng nội bộ. ANSVIS Server nhận video từ camera IP, thực hiện tiền xử lý, suy luận, áp dụng rule, sinh sự kiện kèm snapshot/metadata/thời gian và chuyển kết quả cho hệ thống ngoài qua API.
- [ANSTS](https://doc.anscenter.com.au/docs/ANSTS/Introduction/) hỗ trợ gán nhãn, huấn luyện, đánh giá và triển khai model computer vision tại chỗ khi cần custom/fine-tune. Đây là nhánh có điều kiện, không phải điều kiện chặn Web/App/Backend.
- [Quy trình huấn luyện ANSTS](https://doc.anscenter.com.au/docs/ANSTS/Model_Training/) cung cấp lịch sử thí nghiệm, loss, mAP và validation; [chức năng export](https://doc.anscenter.com.au/docs/ANSTS/Evaluate-Export/) cho phép xuất model theo mục tiêu CPU/GPU nếu baseline/shadow mode không đạt.

Thiết kế dùng ANSVIS làm lớp nhận video và phát sự kiện AI tại trường; backend nghiệp vụ tiếp nhận sự kiện qua API/webhook khả dụng của phiên bản được cấp phép. Facial Recognition dùng cho điểm danh/chấm công nếu consent và enrollment hợp lệ. Bốn pipeline xả rác, hút thuốc, đồng phục và bảo hộ bếp đi theo hướng spec → baseline → shadow → train/fine-tune nếu cần. Happiness index là Optional/Future Scope, không thuộc baseline hiện tại. Các API cụ thể vẫn phải được xác minh trên phiên bản và giấy phép ANSVIS thực tế.

### 0.3 Giả định bắt buộc

| Mã | Giả định/đầu vào | Bên cung cấp | Thời điểm cần có |
|---|---|---|---|
| A01 | Danh sách nghiệp vụ, vai trò, mẫu báo cáo và quy tắc đi trễ/vi phạm đã được phê duyệt | Nhà trường | Trước cuối Tuần 2 |
| A02 | Cơ sở pháp lý, nội dung thông báo và consent của phụ huynh đã được bộ phận pháp lý nhà trường duyệt | Nhà trường | Trước khi nhận dữ liệu sinh trắc học thật |
| A03 | Dữ liệu/pilot sample chỉ cần khi baseline/shadow hoặc custom training; phải được phép sử dụng, ẩn danh khi có thể và có manifest | Nhà trường | Trước từng đợt shadow/custom training |
| A04 | 34 luồng camera/API, tài khoản, IP/port, codec, độ phân giải, FPS và sơ đồ ánh xạ camera–khu vực | Đơn vị camera/nhà trường | Trước Tuần 24; luồng mẫu từ Tuần 3 |
| A05 | Máy chủ/GPU, hệ điều hành, lưu trữ, DNS, chứng thư số và kết nối mạng đã sẵn sàng | Nhà trường/đơn vị hạ tầng | Trước Tuần 24 |
| A06 | License và phiên bản ANSVIS/ANSTS đáp ứng số kênh/model/API cần thiết | Nhà trường/ANSCENTER | Xác nhận trong Tuần 1 |
| A07 | Tài khoản Apple Developer, Google Play Console và nội dung pháp lý của ứng dụng sẵn sàng | Nhà trường | Trước Tuần 20 |
| A08 | Một đầu mối nghiệp vụ có quyền phản hồi và nghiệm thu trong tối đa 2 ngày làm việc | Nhà trường | Xuyên suốt dự án |

### 0.4 Nguyên tắc tiến độ

- Tổng tiến độ cơ sở: **30–34 tuần**, chưa gồm thời gian chờ khách hàng, chờ phần cứng/luồng camera, chờ cấp license hoặc thời gian xét duyệt ngoài kiểm soát của App Store/Google Play.
- Vì chỉ có một developer, các task được thực hiện theo thứ tự phụ thuộc; “nhóm công việc” chỉ là phân loại kỹ năng.
- Bảo mật được đưa vào từng phase. Phase 7 có hoạt động xác nhận bảo mật toàn hệ thống nhưng không thay thế secure-by-design ở các phase trước.
- Mọi chỉ tiêu AI chính thức chỉ được khóa sau khi đánh giá dataset đại diện. AI là công cụ hỗ trợ cảnh báo; kết quả nhạy cảm phải có cơ chế con người xem xét trước khi dùng làm căn cứ xử lý.

---

# PHẦN 1 — TỔNG QUAN CÁC PHASE

| Phase | Thời gian tương đối | Mục tiêu | Deliverable | Exit criteria |
|---|---:|---|---|---|
| 1. Chốt yêu cầu và thiết kế kỹ thuật | Tuần 1–2 | Khóa phạm vi, nghiệp vụ, kiến trúc, dữ liệu, tích hợp ANSCENTER và kiểm soát bảo mật | SRS; kiến trúc; data flow; API contract dự thảo; threat model; backlog; kế hoạch consent | Nhà trường duyệt phạm vi/tiêu chí; rủi ro cao có phương án; đầu vào ANSCENTER được xác nhận |
| 2. Backend và nền tảng bảo mật | Tuần 3–5 | Xây nền backend, dữ liệu, xác thực, sự kiện, CI/CD và kiểm soát truy cập | Môi trường dev/staging; DB; API nền; RBAC/MFA; audit log; secret management; pipeline CI/CD | API nền chạy trên staging; test tự động đạt; không còn lỗ hổng nghiêm trọng đã biết |
| 3. Product Platform core và ANSVIS Adapter | Tuần 6–10 | Hoàn thiện nền Backend, event contract, adapter nhận HTTP Trigger, consent/audit và dữ liệu nghiệp vụ bằng mock/sanitized event | API sự kiện; ANSVIS Adapter; PostgreSQL schema; audit; mock event đủ 6 chức năng | Backend chạy E2E bằng mock event; không phụ thuộc train AI; dữ liệu consent/permission được kiểm soát |
| 4. AI điểm danh/chấm công và 4 pipeline vi phạm | Tuần 11–17 | Dùng Facial Recognition có sẵn; thiết kế/baseline/shadow 4 pipeline vi phạm; train/fine-tune chỉ khi baseline không đạt | Face config; pipeline spec; ROI/rule; shadow report; model/config registry nếu có custom | Mỗi nhóm có metric, human review, rollback; không tự động kết luận sự kiện nhạy cảm nếu chưa nghiệm thu |
| 5. Web Portal | Tuần 18–20 | Cung cấp giao diện phụ huynh/BGH/giáo viên theo đúng phân quyền, dùng API/mock event hoặc event thật khi có | Dashboard; lịch sử; review vi phạm; camera/task health; báo cáo; quản trị; security test web | Nghiệp vụ chính chạy E2E trên staging; kiểm tra quyền không có lỗi mức cao |
| 6. Mobile App React Native | Tuần 20–23 | Cung cấp ứng dụng iOS/Android dùng chung codebase | App đăng nhập; điểm danh/vi phạm; push; secure storage; bản build UAT iOS/Android | Test thiết bị mục tiêu đạt; không lưu token plaintext; build sẵn sàng submit store |
| 7. Tích hợp, kiểm thử, bảo mật và go-live | Tuần 25–29 | Kết nối 34 luồng/API theo nhóm, kiểm thử E2E/tải/an toàn, UAT và phát hành theo đợt | Mapping 34 camera; test report; scan report; backup/restore; runbook; bản production | UAT ký duyệt; không còn lỗi blocker/critical; rollback và incident response đã diễn tập |
| 8. Đào tạo, bàn giao và hỗ trợ vận hành | Tuần 30–34 và hỗ trợ sau đó | Chuyển giao sử dụng/vận hành, hoàn tất nghiệm thu và đưa vào SLA | Hướng dẫn; buổi đào tạo; biên bản bàn giao; SLA; hồ sơ kỹ thuật; báo cáo hyper-care | Các nhóm được đào tạo; tài khoản/tài liệu bàn giao an toàn; biên bản nghiệm thu được ký |

---

# PHẦN 2 — QUY TRÌNH LÀM VIỆC CHI TIẾT (WORKFLOW/SOP)

## 2.1 Quy trình phát triển phần mềm

1. **Tiếp nhận yêu cầu:** mỗi yêu cầu phải có người yêu cầu, giá trị nghiệp vụ, dữ liệu liên quan, tiêu chí chấp nhận và mức ưu tiên.
2. **Phân tích tác động:** developer kiểm tra tác động tới API, AI, web/app, dữ liệu cá nhân, hiệu năng và lịch phát hành.
3. **Tạo ticket:** task giới hạn 1–3 ngày, ghi rõ phụ thuộc, Definition of Done (DoD), test và yêu cầu bảo mật.
4. **Quản lý mã nguồn:** `main` là production, `develop` là staging, `feature/*` cho tính năng và `hotfix/*` cho lỗi khẩn cấp. Cấm commit trực tiếp vào `main`.
5. **Tự review có kiểm soát:** do chỉ có một developer, mọi thay đổi vẫn đi qua Pull Request; developer dùng checklist chức năng, OWASP, dữ liệu cá nhân, migration và rollback. CI đóng vai trò kiểm tra độc lập tự động. Hạng mục rủi ro cao được khuyến nghị mời bên thứ ba review trước go-live.
6. **CI:** kiểm tra format/lint, unit test, dependency scan, secret scan, SAST (phân tích mã nguồn tìm lỗi bảo mật) và build artifact có version.
7. **Triển khai staging:** tự động từ `develop`; migration được backup và thử rollback; smoke test chạy sau deploy.
8. **UAT:** nhà trường chạy kịch bản chấp nhận trên staging, ghi nhận bằng ticket; thay đổi phạm vi phải qua change request.
9. **Triển khai production:** chỉ từ tag/release đã duyệt; cần approval thủ công, backup trước deploy, theo dõi log/metric và sẵn sàng rollback.
10. **Hậu kiểm:** theo dõi 24–48 giờ, đóng release khi không còn lỗi nghiêm trọng và cập nhật changelog/runbook.

## 2.2 Quy trình baseline, shadow mode và huấn luyện model AI khi cần

1. Xác định bài toán, class, hành vi, vùng quan sát, điều kiện ánh sáng, khoảng cách và trường hợp không được kết luận.
2. Kiểm kê model/task hiện có trong ANSVIS và xác định phần nào dùng được ngay, phần nào chỉ làm baseline.
3. Cấu hình ROI/rule/threshold/tracker và chạy baseline bằng model/rule hiện có nếu có thể.
4. Chạy shadow mode trên luồng thật hoặc sample hợp lệ: hệ thống ghi nhận nhưng chưa phát cảnh báo/kết luận chính thức.
5. Đánh giá false positive, false negative, latency, false alerts/camera/giờ và các tình huống dễ nhầm.
6. Chỉ chuyển sang dataset/label/train/fine-tune khi baseline/shadow không đạt hoặc thiếu class cần nhận diện.
7. Nếu phải train: chỉ nhận dữ liệu có nguồn gốc, mục đích và consent hợp lệ; lập manifest, checksum, người duyệt, retention và ngày phải xóa.
8. Loại dữ liệu không liên quan; che/ẩn danh khuôn mặt khi bài toán không cần nhận diện danh tính.
9. Gán nhãn theo guideline; kiểm tra chéo mẫu nhãn và thống kê mất cân bằng class.
10. Tạo experiment có version trong ANSTS hoặc công cụ được duyệt; lưu model type, tham số, dataset version, metric và checksum.
11. Đánh giá model/config trên test set độc lập; với nhận diện khuôn mặt đo FAR/FRR, với detection đo precision/recall/F1/mAP nếu có dataset đủ chuẩn.
12. Đóng gói model/config có checksum, version, threshold/ROI, hướng dẫn rollback; shadow mode lại trước production.

## 2.3 Quy trình tích hợp luồng camera/API có sẵn

1. Nhận phiếu bàn giao gồm camera ID, khu vực, mục đích, RTSP/ONVIF/API endpoint, codec, FPS, độ phân giải, credential, IP allowlist và thời gian khả dụng.
2. Credential được đưa thẳng vào secret manager; không gửi qua ticket/email hoặc ghi trong source code.
3. Kiểm tra kết nối từ môi trường ANSVIS/server; ghi nhận độ trễ, mất khung hình và khả năng tự kết nối lại.
4. Ánh xạ camera với đúng pipeline/model/ROI/rule; không xử lý khu vực ngoài phạm vi đã duyệt.
5. Kiểm tra event output từ ANSVIS: schema, event ID, camera ID, timestamp, class, confidence, snapshot và chữ ký/xác thực request nếu API hỗ trợ.
6. Backend kiểm tra schema, chống gửi lặp bằng idempotency key, giới hạn kích thước, timeout và retry có backoff.
7. Chạy luồng mẫu và shadow mode; đối soát thời gian camera/server, cảnh báo giả và khả năng mất kết nối.
8. Lập biên bản xác nhận từng camera. Lỗi thiết bị/mạng vật lý được chuyển đúng đơn vị phụ trách, không ghi thành task lắp đặt của developer.

## 2.4 Quy trình kiểm thử tích hợp toàn hệ thống

1. Khóa phiên bản phần mềm, model, cấu hình ANSVIS và dữ liệu test.
2. Chuẩn bị ma trận vai trò: phụ huynh chỉ xem con mình; giáo viên xem dữ liệu được giao; BGH xem tổng hợp; admin quản trị có audit.
3. Test luồng chuẩn: camera → ANSVIS → event/API → backend → database → web/app → thông báo → báo cáo.
4. Test trường hợp lỗi: mất camera, event trùng, timestamp sai, model timeout, hết dung lượng, push thất bại và API ngoài không phản hồi.
5. Test quyền truy cập bằng cả giao diện và gọi API trực tiếp; kiểm tra truy cập chéo giữa phụ huynh.
6. Test tải với 34 camera theo event rate dự kiến và burst; đo độ trễ, CPU/GPU, RAM, DB và hàng đợi.
7. Test backup/restore, rollback phiên bản phần mềm/model và khởi động lại dịch vụ.
8. Quét bảo mật, sửa lỗi theo mức độ; blocker/critical phải bằng 0 trước go-live.
9. Nhà trường chạy UAT theo kịch bản và ký kết quả; lỗi được phân loại blocker/major/minor.
10. Regression test sau sửa lỗi, phát hành release candidate cuối và lưu toàn bộ bằng chứng kiểm thử.

## 2.5 Quy trình đào tạo và bàn giao

1. Phân nhóm người học: phụ huynh; giáo viên/cán bộ; BGH; quản trị vận hành.
2. Chuẩn bị tài liệu ngắn theo vai trò, video thao tác, FAQ, quy định quyền riêng tư và kênh hỗ trợ.
3. Tạo tài khoản demo không dùng dữ liệu trẻ em thật; cấp tài khoản thật qua kênh an toàn sau đào tạo.
4. Đào tạo phụ huynh: đăng nhập, consent, xem dữ liệu của con, nhận thông báo, gửi yêu cầu chỉnh sửa/xóa dữ liệu.
5. Đào tạo giáo viên/BGH: dashboard, xác minh cảnh báo, báo cáo, xử lý false positive và quy tắc không dùng AI làm quyết định duy nhất.
6. Đào tạo quản trị: user/role, MFA, audit log, backup, health dashboard, model/config version, escalation và incident response.
7. Kiểm tra lại bằng bài thực hành; ghi nhận người tham dự và vấn đề còn mở.
8. Bàn giao source/artifact theo hợp đồng, tài liệu kiến trúc/API/runbook, danh mục tài khoản và biên bản nghiệm thu; tuyệt đối không ghi mật khẩu trong biên bản.

## 2.6 Quy trình xử lý sự cố và hỗ trợ sau bàn giao

| Mức | Ví dụ | Phản hồi ban đầu | Mục tiêu khôi phục/giải pháp tạm |
|---|---|---:|---:|
| P1 – Nghiêm trọng | Hệ thống ngừng toàn bộ; nghi rò rỉ dữ liệu; sai quyền diện rộng | 30 phút trong giờ hỗ trợ; hotline khẩn cấp | 4 giờ hoặc kích hoạt phương án cô lập/rollback |
| P2 – Cao | Một chức năng chính/cụm camera không hoạt động, chưa có dấu hiệu rò rỉ | 2 giờ làm việc | 1 ngày làm việc |
| P3 – Trung bình | Lỗi cục bộ, có cách xử lý tạm | 4 giờ làm việc | 3 ngày làm việc |
| P4 – Thấp/Yêu cầu | Hỏi đáp, cải tiến nhỏ | 1 ngày làm việc | Lên lịch bản phát hành kế tiếp |

Quy trình: tiếp nhận qua cổng ticket/email; P1 đồng thời gọi hotline → cấp mã sự cố → xác nhận phạm vi/ảnh hưởng → bảo toàn log → cô lập hoặc rollback → cập nhật trạng thái theo chu kỳ → xác nhận khôi phục với nhà trường → phân tích nguyên nhân gốc trong 2 ngày làm việc với P1/P2 → tạo hành động phòng ngừa. SLA chính thức phụ thuộc hợp đồng và khung giờ hỗ trợ được ký.

## 2.7 Quy trình bảo mật xuyên suốt

### A. Threat modeling

1. Lập sơ đồ luồng dữ liệu từ camera tới ANSVIS, backend, storage, web/app và hệ thống thông báo.
2. Phân loại dữ liệu: công khai, nội bộ, cá nhân, cá nhân nhạy cảm/sinh trắc học.
3. Dùng STRIDE để nhận diện giả mạo, sửa dữ liệu, chối bỏ, lộ lọt, từ chối dịch vụ và leo thang đặc quyền.
4. Mỗi rủi ro có owner, mức độ, biện pháp, bằng chứng test và thời hạn; cập nhật khi có API/model/luồng dữ liệu mới.

### B. Secure coding và review

- Pull Request bắt buộc có checklist OWASP Top 10: kiểm soát truy cập; mã hóa; injection; thiết kế không an toàn; cấu hình; thư viện lỗi thời; xác thực; tính toàn vẹn phần mềm/dữ liệu; logging; SSRF.
- Kiểm tra riêng: object-level authorization giữa phụ huynh–học sinh, upload file, webhook giả mạo, event lặp, mass assignment, rate limit và lỗi không làm lộ dữ liệu.
- CI phải chạy unit/integration test, SAST, dependency scan, secret scan; mức Critical/High phải được xử lý hoặc có chấp thuận rủi ro bằng văn bản.

### C. Quản lý secrets

- API key, DB password, camera credential, signing key và push credential chỉ lưu trong secret manager/secure CI variables.
- Tách secrets theo dev/staging/production, cấp quyền tối thiểu, bật audit và luân chuyển định kỳ hoặc ngay khi nghi lộ.
- Cấm hard-code, commit file `.env`, chụp màn hình hoặc đưa secrets vào log/ticket/tài liệu bàn giao.

### D. Mã hóa và vòng đời dữ liệu

- API và quản trị dùng TLS 1.2+; kết nối camera đi qua mạng tin cậy/VPN khi phải vượt qua vùng mạng không tin cậy.
- Database, object storage, backup và face embedding được mã hóa at-rest; khóa mã hóa tách khỏi dữ liệu.
- Ưu tiên lưu face embedding đã mã hóa thay vì ảnh khuôn mặt gốc. Snapshot chỉ lưu khi có mục đích, consent và thời hạn rõ ràng.
- Chính sách retention tự động xóa; log xóa có audit. Happiness index chỉ dùng dạng tổng hợp/ẩn danh và không dùng cho quyết định kỷ luật cá nhân.

### E. Checklist kiểm thử bảo mật trước go-live

- [ ] TLS hợp lệ, không dùng giao thức/yếu tố mã hóa lỗi thời.
- [ ] MFA bắt buộc cho Admin/BGH; token ngắn hạn, refresh rotation và revoke hoạt động.
- [ ] RBAC/API authorization test đủ vai trò; phụ huynh không truy cập dữ liệu trẻ khác.
- [ ] Rate limit, validation, giới hạn upload/payload và chống event replay hoạt động.
- [ ] Secret scan sạch; production secrets không xuất hiện trong source/log/artifact.
- [ ] Dependency/container/SAST/DAST scan không còn Critical/High chưa xử lý.
- [ ] Log không chứa token, mật khẩu, face embedding hoặc ảnh không cần thiết.
- [ ] Backup mã hóa và restore test thành công.
- [ ] Mobile dùng Keychain/Keystore, certificate validation/pinning theo thiết kế, chống screenshot ở màn hình nhạy cảm nếu được duyệt.
- [ ] Pentest cơ bản cho đăng nhập, reset mật khẩu, IDOR, injection, upload, webhook/API và cấu hình cloud/server.
- [ ] Incident contacts, rollback, kill switch và bằng chứng consent sẵn sàng.

### F. Incident Response Plan

1. **Phát hiện:** cảnh báo SIEM/log, báo cáo người dùng hoặc scan; mở incident và bảo toàn bằng chứng.
2. **Phân loại:** xác định dữ liệu/người bị ảnh hưởng, vector tấn công, mức P1–P4 và nghĩa vụ pháp lý.
3. **Cô lập:** thu hồi token/key, khóa tài khoản, chặn endpoint, cô lập service/model hoặc chuyển chế độ chỉ đọc.
4. **Khắc phục:** vá lỗi, rotate secrets, khôi phục bản sạch, kiểm tra persistence và regression.
5. **Thông báo:** báo đầu mối nhà trường ngay theo SLA; nhà trường/pháp lý quyết định nội dung và thời hạn thông báo phụ huynh/cơ quan có thẩm quyền khi có rò rỉ.
6. **Phục hồi:** mở lại theo từng bước, giám sát tăng cường và xác nhận tính toàn vẹn.
7. **Rút kinh nghiệm:** báo cáo nguyên nhân gốc, timeline, ảnh hưởng và hành động phòng ngừa; cập nhật threat model/runbook.

### G. Consent dữ liệu sinh trắc học trẻ em

1. Nhà trường/pháp lý xác định căn cứ xử lý, mục đích, loại dữ liệu, thời hạn lưu, bên nhận dữ liệu và quyền rút consent.
2. Phụ huynh/người giám hộ nhận thông báo dễ hiểu và thực hiện đồng ý chủ động; không dùng ô chọn mặc định.
3. Backend lưu version nội dung consent, người đồng ý, thời gian, bằng chứng và phạm vi; consent phải kiểm tra trước khi enroll khuôn mặt.
4. Trẻ không có consent phải có phương án điểm danh thay thế và không bị đưa vào tập huấn luyện.
5. Khi rút consent: ngừng xử lý, xóa/ẩn danh dữ liệu theo quy định, ghi audit và phản hồi hoàn thành.
6. Nội dung pháp lý cuối cùng phải do nhà trường/đơn vị tư vấn pháp luật phê duyệt; tài liệu này không thay thế tư vấn pháp lý.

---

# PHẦN 3 — DANH SÁCH ISSUE/TASK CHI TIẾT

> Tất cả task do cùng một developer thực hiện. Thời lượng là ngày công tập trung; thứ tự phụ thuộc là cơ sở lập lịch tuần tự. Hoạt động chờ phản hồi/duyệt không được tính là ngày công.

## Phase 1 — Chốt yêu cầu và thiết kế kỹ thuật (Tuần 1–2)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| DES-01 | Xác nhận phạm vi và stakeholder | Khóa 34 camera, module, vai trò, ngoài phạm vi và đầu mối duyệt | 1 | PM | Cao | Không | Biên bản scope và RACI được duyệt | 1 ngày |
| DES-02 | Chuẩn hóa use case và quy tắc nghiệp vụ | Mô tả điểm danh, đi trễ, vi phạm và chấm công theo sáu chức năng baseline | 1 | PM | Cao | DES-01 | Use case có input/output/ngoại lệ/acceptance | 2 ngày |
| DES-03 | Xác minh khả năng ANSCENTER | Kiểm tra version, license, số kênh, model, API/event và export | 1 | AI | Cao | DES-02 | Ma trận supported/gap và câu hỏi đã đóng | 1 ngày |
| DES-04 | Thiết kế kiến trúc logic | Thiết kế ANSVIS, AI, backend, DB, web/app, notification | 1 | Backend | Cao | DES-03 | Sơ đồ thành phần và interface được duyệt | 1 ngày |
| DES-05 | Thiết kế dữ liệu và API contract | Định nghĩa entity, event schema, API, lỗi, idempotency | 1 | Backend | Cao | DES-04 | ERD và OpenAPI/event contract bản 1 | 2 ngày |
| DES-06 | Thiết kế UX luồng chính | Wireflow theo vai trò, review cảnh báo và consent | 1 | Web/Mobile | TB | DES-05 | Wireflow và danh sách màn hình được duyệt | 1 ngày |
| DES-07 | Lập data management plan | Nguồn, mục đích, retention, xóa và quyền truy cập dữ liệu | 1 | Security/DevOps | Cao | DES-05 | Data inventory và retention matrix hoàn tất | 1 ngày |
| DES-08 | Threat model ban đầu | Phân tích STRIDE cho camera–ANSVIS–backend–client | 1 | Security/DevOps | Cao | DES-07 | Threat register có biện pháp/risk owner | 1 ngày |
| DES-09 | Thiết kế consent và quyền riêng tư | Xác định flow consent, rút consent, phương án thay thế | 1 | Security/DevOps | Cao | DES-08 | Flow và yêu cầu pháp lý gửi nhà trường duyệt | 1 ngày |
| DES-10 | Lập backlog và baseline nghiệm thu | Phân rã task, phụ thuộc, ngưỡng AI/UAT, change control | 1 | PM | Cao | DES-09 | Backlog baseline và milestone được ký duyệt | 1 ngày |

## Phase 2 — Backend và nền tảng bảo mật (Tuần 3–5)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| BE-01 | Khởi tạo repository và chuẩn chất lượng | Cấu trúc source, branching, lint, test, versioning | 2 | Backend | Cao | DES-10 | Repo build được; branch protection/checklist sẵn sàng | 1 ngày |
| BE-02 | Dựng môi trường dev/staging bằng container | Đóng gói backend, DB, cache/queue và cấu hình môi trường | 2 | Backend | Cao | BE-01 | Một lệnh dựng được staging tương đương | 2 ngày |
| BE-03 | Tạo schema và migration nền | User, role, student, staff, camera, event, consent, audit | 2 | Backend | Cao | BE-02 | Migration up/down và test dữ liệu mẫu đạt | 2 ngày |
| BE-04 | Xây authentication và session | Login, refresh rotation, revoke, reset password | 2 | Security/DevOps | Cao | BE-03 | Test token/session và chống brute force đạt | 2 ngày |
| BE-05 | Xây RBAC và MFA | Quyền API theo vai trò; MFA bắt buộc Admin/BGH | 2 | Security/DevOps | Cao | BE-04 | Authorization matrix test đủ vai trò | 2 ngày |
| BE-06 | Thiết lập secret management và TLS staging | Tách secret, rotation procedure, HTTPS cho API | 2 | Security/DevOps | Cao | BE-05 | Không có secret trong repo; TLS test đạt | 1 ngày |
| BE-07 | Xây API danh mục lõi | CRUD có kiểm soát cho người dùng, học sinh, cán bộ, camera | 2 | Backend | Cao | BE-06 | OpenAPI cập nhật; unit/integration test đạt | 2 ngày |
| BE-08 | Xây event ingestion | Nhận event ANSVIS/API, validate, idempotency, retry | 2 | Backend | Cao | BE-07 | Event hợp lệ lưu đúng; trùng/sai bị xử lý an toàn | 2 ngày |
| BE-09 | Xây audit log và quan sát hệ thống | Log hành động nhạy cảm, metric, trace ID, health check | 2 | Security/DevOps | Cao | BE-08 | Audit bất biến logic; log không lộ dữ liệu nhạy cảm | 1 ngày |
| BE-10 | Thiết lập CI/CD staging | Test, SAST, dependency/secret scan, build/deploy | 2 | Backend | Cao | BE-09 | Pipeline xanh; deploy staging và rollback thử thành công | 2 ngày |
| BE-11 | Kiểm thử backend nền | Test API, quyền, lỗi, tải cơ sở và backup/restore | 2 | QA | Cao | BE-10 | Báo cáo test; không còn blocker/high | 2 ngày |

## Phase 3 — Product Platform core và ANSVIS Adapter (Tuần 6–10)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| PF-01 | Định nghĩa event contract tối thiểu từ ANSVIS | Schema version, event type, camera, confidence, evidence reference | 3 | Backend | Cao | BE-11 | Contract có fixture sạch đủ 6 chức năng | 2 ngày |
| PF-02 | Xây ANSVIS Adapter skeleton | Webhook route, parser, normalized event model | 3 | Backend | Cao | PF-01 | Raw ANSVIS field không lan sang business service | 2 ngày |
| PF-03 | Bảo vệ webhook ANSVIS | Token/HMAC/source validation, size limit, replay guard | 3 | Security/DevOps | Cao | PF-02 | Request giả/trùng/quá cỡ bị chặn an toàn | 2 ngày |
| PF-04 | Xây idempotency và event ingestion | Chống trùng, queue/outbox, retry, DLQ | 3 | Backend | Cao | PF-03 | Event trùng không tạo bản ghi/thông báo trùng | 2 ngày |
| PF-05 | Xây consent gate cho biometric | Chặn xử lý/enrollment face nếu thiếu/rút consent | 3 | Security/DevOps | Cao | PF-04 | Test có/không/rút consent đều đạt | 2 ngày |
| PF-06 | Xây attendance/timekeeping business rule bằng mock face event | Có mặt/vắng/đi muộn/check-in/out, ca làm | 3 | Backend | Cao | PF-05 | Kịch bản điểm danh/chấm công chính chạy E2E bằng mock event | 3 ngày |
| PF-07 | Xây violation review model bằng mock event | Review state, human confirmation, appeal/correction | 3 | Backend | Cao | PF-06 | Sự kiện nhạy cảm không tự động kết luận khi chưa review | 2 ngày |
| PF-08 | Xây evidence metadata policy | Private object storage, signed URL, không base64 mặc định | 3 | Security/DevOps | Cao | PF-07 | Không lưu media binary trong DB, có audit khi xem/export | 2 ngày |
| PF-09 | Xây camera/task registry | Camera, khu vực, ANSVIS mapping, task, ROI, schedule, status | 3 | Backend | Cao | PF-08 | Có mapping phục vụ 34 camera và dashboard health | 2 ngày |
| PF-10 | Contract test với sanitized payload | Payload hợp lệ/sai/trùng/thiếu field | 3 | QA | Cao | PF-09 | Test pass, không có dữ liệu thật trong fixture | 2 ngày |
| PF-11 | Kiểm thử phân quyền dữ liệu nền | Parent/teacher/BGH/admin object-level authorization | 3 | Security/DevOps | Cao | PF-10 | Không có lỗi truy cập chéo dữ liệu | 2 ngày |

## Phase 4 — AI điểm danh/chấm công và 4 pipeline vi phạm (Tuần 11–17)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| AI-01 | Cấu hình Facial Recognition có sẵn | Face Detection/Facial Recognition, group/person, threshold, Event Log | 4 | AI | Cao | PF-11 | Nhận được face event có confidence và low-confidence state | 2 ngày |
| AI-02 | Xác nhận enrollment/consent/unknown face flow | Quy trình đăng ký/rút consent, unknown, manual correction | 4 | Security/DevOps | Cao | AI-01 | Không xử lý face khi thiếu consent; audit đầy đủ | 2 ngày |
| AI-03 | Viết spec Kitchen PPE pipeline | Class/rule/ROI/event/human review cho khu bếp | 4 | AI | Cao | AI-02 | Pipeline spec có mũ/khẩu trang/tạp dề/găng/đồng phục/giày | 2 ngày |
| AI-04 | Viết spec Student Uniform pipeline | Quy định đồng phục, class/rule, case che khuất/không chắc chắn | 4 | AI | Cao | AI-03 | Spec được duyệt trước khi baseline/train | 2 ngày |
| AI-05 | Viết spec Littering pipeline | Person/object tracking, left-object, allowed trash zone | 4 | AI | Cao | AI-04 | Xả rác được định nghĩa là hành vi, không chỉ object detection | 2 ngày |
| AI-06 | Viết spec Smoking pipeline | Cigarette/vape/hand-to-mouth/smoke nếu có, suspected-only | 4 | AI | Cao | AI-05 | Có human review bắt buộc và false-positive list | 2 ngày |
| AI-07 | Chạy baseline bằng model/rule hiện có | GenericOD/Objects/Helmet/FireSmoke nếu phù hợp | 4 | AI | Cao | AI-06 | Có baseline report, không dùng làm cam kết production | 3 ngày |
| AI-08 | Cấu hình ROI/rule/threshold/tracker theo camera mẫu | Tối ưu vùng quan sát và giảm cảnh báo sai | 4 | AI | Cao | AI-07 | Config versioned theo camera/task | 2 ngày |
| AI-09 | Chạy shadow mode từng pipeline | Ghi nhận nhưng chưa tự động kết luận/disciplinary action | 4 | QA | Cao | AI-08 | Shadow report có FP/FN/latency/event sample đã kiểm soát | 3 ngày |
| AI-10 | Chuẩn bị dataset/label/train nếu baseline không đạt | Manifest, sanitization, label guideline, retention | 4 | Security/DevOps | Có điều kiện | AI-09 | Không có dữ liệu thật trong Git; dataset có approval/audit | 2 ngày |
| AI-11 | Train/fine-tune/import model khi cần | ANSTS/model import, evaluate, checksum, model card | 4 | AI | Có điều kiện | AI-10 | Chỉ áp dụng cho pipeline chưa đạt; có metric và rollback | 3 ngày |
| AI-12 | Chốt model/config registry và nghiệm thu pipeline | Version, checksum/config hash, approval, rollback | 4 | QA | Cao | AI-11 hoặc AI-09 | Pipeline chỉ bật production sau sign-off | 2 ngày |

## Phase 5 — Web Portal (Tuần 18–20)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| WEB-01 | Khởi tạo web và design system | Routing, layout, component, responsive và error boundary | 5 | Web | Cao | PF-11 | Build staging; layout mục tiêu hoạt động | 1 ngày |
| WEB-02 | Xây đăng nhập, MFA và session UX | Login, MFA, hết phiên, revoke và lỗi an toàn | 5 | Security/DevOps | Cao | WEB-01 | Test session/MFA; không lộ token qua URL/log | 2 ngày |
| WEB-03 | Xây cổng phụ huynh | Điểm danh, lịch sử vi phạm và thông tin của con | 5 | Web | Cao | WEB-02 | Phụ huynh chỉ thấy con được liên kết | 2 ngày |
| WEB-04 | Xây dashboard BGH | Tổng quan, xu hướng, bộ lọc thời gian/khu vực/loại | 5 | Web | Cao | WEB-03 | Số liệu đối soát với DB và test dữ liệu rỗng | 2 ngày |
| WEB-05 | Xây cổng cán bộ/giáo viên | Chấm công cá nhân và chỉ số tổng hợp phù hợp quyền | 5 | Web | TB | WEB-04 | Dữ liệu cá nhân/tổng hợp hiển thị đúng scope | 1 ngày |
| WEB-06 | Xây màn hình review cảnh báo | Xem bằng chứng, xác nhận false positive và ghi chú | 5 | Web | Cao | WEB-05 | Mọi chỉnh sửa có người/thời gian/lý do | 2 ngày |
| WEB-07 | Xây báo cáo và xuất file | Báo cáo điểm danh/vi phạm/chấm công Excel/PDF | 5 | Web | Cao | WEB-06 | File đúng bộ lọc, chống formula injection | 2 ngày |
| WEB-08 | Xây quản trị consent và yêu cầu dữ liệu | Tra cứu consent, rút, yêu cầu sửa/xóa và trạng thái | 5 | Web | Cao | WEB-07 | Workflow có audit và kiểm tra quyền | 2 ngày |
| WEB-09 | Hardening frontend | CSP, security headers, XSS/CSRF, upload/download an toàn | 5 | Security/DevOps | Cao | WEB-08 | Header scan và test XSS/CSRF đạt | 2 ngày |
| WEB-10 | Kiểm thử accessibility và responsive | Trình duyệt, bàn phím, kích thước màn hình, thông báo lỗi | 5 | QA | TB | WEB-09 | Kịch bản trình duyệt mục tiêu đạt | 1 ngày |
| WEB-11 | Kiểm thử phân quyền E2E web | Thử truy cập chéo, URL trực tiếp và API bị sửa tham số | 5 | Security/DevOps | Cao | WEB-10 | Không có lỗi IDOR/broken access mức cao | 2 ngày |

## Phase 6 — Mobile App React Native (Tuần 20–23)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| MOB-01 | Khởi tạo React Native và build pipeline | Cấu trúc app, env, signing dev, build iOS/Android | 6 | Mobile | Cao | WEB-11 | CI tạo được hai bản build thử nghiệm | 2 ngày |
| MOB-02 | Xây navigation và API client | Luồng theo vai trò, timeout, retry và error handling | 6 | Mobile | Cao | MOB-01 | Navigation/API mock và offline error đạt | 2 ngày |
| MOB-03 | Xây đăng nhập và MFA | Login, MFA, refresh/revoke và đăng xuất mọi thiết bị | 6 | Mobile | Cao | MOB-02 | Auth test trên iOS/Android đạt | 2 ngày |
| MOB-04 | Thiết lập secure storage | Token trong Keychain/Keystore, không dùng AsyncStorage | 6 | Security/DevOps | Cao | MOB-03 | Kiểm tra storage/log không có token plaintext | 1 ngày |
| MOB-05 | Cấu hình certificate validation/pinning | Ràng buộc certificate theo thiết kế và cơ chế rotation | 6 | Security/DevOps | Cao | MOB-04 | MITM test thất bại an toàn; rotation runbook có sẵn | 2 ngày |
| MOB-06 | Xây màn hình điểm danh/chấm công | Danh sách, lịch, trạng thái và chi tiết | 6 | Mobile | Cao | MOB-05 | Dữ liệu khớp web/API; empty/error state đủ | 2 ngày |
| MOB-07 | Xây màn hình vi phạm và review | Danh sách, ảnh bằng chứng được phép, phản hồi sai | 6 | Mobile | Cao | MOB-06 | Quyền và audit review hoạt động | 2 ngày |
| MOB-08 | Xây push notification | Đăng ký device token, deep link, opt-in và revoke | 6 | Mobile | Cao | MOB-07 | Push đúng user; logout vô hiệu token | 2 ngày |
| MOB-09 | Xây consent và quyền riêng tư trên app | Xem/rút consent, yêu cầu dữ liệu và thông báo chính sách | 6 | Mobile | Cao | MOB-08 | Version consent và audit đồng bộ backend | 2 ngày |
| MOB-10 | Hardening bản production | Ẩn log, obfuscation phù hợp, chặn debug config/release secret | 6 | Security/DevOps | Cao | MOB-09 | Mobile security checklist không còn high | 2 ngày |
| MOB-11 | Test thiết bị và chuẩn bị store | Regression, permission text, privacy label, screenshot/listing | 6 | QA | Cao | MOB-10 | Bản UAT hai nền tảng và hồ sơ submit sẵn sàng | 3 ngày |

## Phase 7 — Tích hợp, kiểm thử, bảo mật và go-live (Tuần 24–27)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| INT-01 | Kiểm tra phiếu bàn giao 34 luồng/API | Validate endpoint, codec, FPS, time sync và credential | 7 | AI | Cao | MOB-11, A04 | Ma trận 34 camera có trạng thái và bằng chứng | 2 ngày |
| INT-02 | Ánh xạ camera–pipeline–khu vực | Gán đúng model, ROI, rule và mục đích xử lý | 7 | AI | Cao | INT-01 | 34 mapping được nhà trường xác nhận | 2 ngày |
| INT-03 | Tích hợp ANSVIS với backend production-like | Kết nối event/API, reconnect, retry và idempotency | 7 | Backend | Cao | INT-02 | Luồng E2E chạy ổn định trên staging | 2 ngày |
| INT-04 | Chạy shadow mode toàn hệ thống | Đo false alert, latency, loss và tải trên luồng thật | 7 | QA | Cao | INT-03 | Báo cáo tối thiểu theo cửa sổ UAT đã duyệt | 3 ngày |
| INT-05 | Kiểm thử E2E và regression | Camera đến web/app/notification/report, gồm lỗi ngoại lệ | 7 | QA | Cao | INT-04 | 100% critical scenarios pass | 3 ngày |
| INT-06 | Kiểm thử tải và khả năng phục hồi | Event burst, restart, queue backlog, storage và fail recovery | 7 | QA | Cao | INT-05 | Đạt SLA hiệu năng hoặc có capacity plan duyệt | 2 ngày |
| INT-07 | Quét lỗ hổng và pentest cơ bản | SAST/DAST/dependency/container/API/mobile checks | 7 | Security/DevOps | Cao | INT-06 | Critical/High bằng 0; Medium có kế hoạch | 2 ngày |
| INT-08 | Rà soát privacy và consent production | Retention, xóa, export, log, backup và dữ liệu không consent | 7 | Security/DevOps | Cao | INT-07 | Privacy checklist và bằng chứng xóa đạt | 2 ngày |
| INT-09 | Diễn tập backup, rollback và security incident | Restore DB, rollback app/model, revoke key và cô lập service | 7 | Security/DevOps | Cao | INT-08 | RTO/RPO đo được; biên bản diễn tập hoàn tất | 2 ngày |
| INT-10 | Tổ chức UAT và xử lý lỗi | Nhà trường chạy acceptance, developer sửa tuần tự | 7 | QA | Cao | INT-09 | UAT sign-off; blocker/critical bằng 0 | 3 ngày |
| INT-11 | Phát hành production và submit app | Tag release, deploy, smoke test, submit store | 7 | Backend/Mobile | Cao | INT-10 | Web/backend live; app submitted; rollback sẵn sàng | 2 ngày |
| INT-12 | Giám sát go-live 24–48 giờ | Theo dõi log/metric/model, xử lý sự cố và báo cáo | 7 | QA | Cao | INT-11 | Không còn P1/P2 mở; báo cáo go-live phát hành | 2 ngày |

## Phase 8 — Đào tạo, bàn giao và hỗ trợ vận hành (Tuần 30–34)

| ID | Tên task | Mô tả ngắn | Phase | Nhóm công việc | Ưu tiên | Phụ thuộc | Definition of Done | Ước tính |
|---|---|---|---|---|---|---|---|---|
| TRN-01 | Soạn hướng dẫn theo vai trò | Tài liệu phụ huynh, giáo viên, BGH, admin và FAQ | 8 | PM | Cao | INT-12 | Tài liệu khớp release production | 2 ngày |
| TRN-02 | Soạn runbook kỹ thuật | Monitoring, backup, restore, model, deploy và escalation | 8 | Backend | Cao | TRN-01 | Admin thực hiện được kịch bản mẫu | 2 ngày |
| TRN-03 | Chuẩn bị môi trường và dữ liệu đào tạo | Tài khoản demo, dữ liệu giả, bài thực hành | 8 | QA | TB | TRN-02 | Không dùng dữ liệu trẻ em thật; demo chạy ổn định | 1 ngày |
| TRN-04 | Đào tạo phụ huynh/giáo viên | Sử dụng app/web, consent, phản hồi cảnh báo sai | 8 | PM | Cao | TRN-03 | Có danh sách tham dự và Q&A | 1 ngày |
| TRN-05 | Đào tạo BGH/admin | Dashboard, báo cáo, RBAC, MFA, audit và vận hành | 8 | PM | Cao | TRN-04 | Học viên hoàn thành bài thực hành | 1 ngày |
| TRN-06 | Bàn giao tài khoản và secrets an toàn | Chuyển quyền owner, MFA, recovery và rotation | 8 | Security/DevOps | Cao | TRN-05 | Không có password trong tài liệu; biên bản quyền sở hữu | 1 ngày |
| TRN-07 | Bàn giao hồ sơ privacy/security | Threat model, scan, consent, retention và IR plan | 8 | Security/DevOps | Cao | TRN-06 | Hồ sơ được đầu mối nhà trường tiếp nhận | 1 ngày |
| TRN-08 | Diễn tập tiếp nhận sự cố với nhà trường | Chạy tabletop P1 rò rỉ/gián đoạn và tuyến thông báo | 8 | Security/DevOps | Cao | TRN-07 | Contact tree và thời gian phản ứng được xác nhận | 1 ngày |
| TRN-09 | Chốt SLA và kênh hỗ trợ | Mức P1–P4, giờ hỗ trợ, contact và escalation | 8 | PM | Cao | TRN-08 | SLA/phụ lục hỗ trợ được ký | 1 ngày |
| TRN-10 | Bàn giao kỹ thuật và nghiệm thu | Source/artifact/tài liệu/license inventory/changelog | 8 | PM | Cao | TRN-09 | Checklist bàn giao và biên bản nghiệm thu ký | 2 ngày |
| TRN-11 | Review sau hyper-care | Tổng hợp KPI, sự cố, false alert và backlog cải tiến | 8 | PM | TB | TRN-10 + thời gian vận hành | Báo cáo review và backlog được thống nhất | 1 ngày |

---

# PHẦN 4 — BẢNG RỦI RO VÀ PHƯƠNG ÁN DỰ PHÒNG

| ID | Phase | Rủi ro | Khả năng | Ảnh hưởng | Phương án phòng ngừa/dự phòng | Chủ trì |
|---|---|---|---|---|---|---|
| R01 | 1 | Yêu cầu thay đổi sau khi đã phát triển | TB | Cao | Khóa baseline; mọi thay đổi có phân tích thời gian/chi phí và phê duyệt change request | Nhà trường + developer |
| R02 | 1 | License/phiên bản ANSCENTER không có đủ API, số kênh hoặc model | TB | Cao | Xác minh proof-of-capability Tuần 1; dùng adapter hoặc công cụ thay thế được duyệt nếu có gap | Nhà trường/ANSCENTER + developer |
| R03 | 1–8 | Một developer là điểm nghẽn duy nhất | TB | Cao | Lập tài liệu liên tục, backup repo/artifact, giới hạn WIP, có kế hoạch người tiếp nhận khẩn cấp từ khách hàng/nhà cung cấp | Hai bên |
| R04 | 2 | Máy chủ/môi trường không sẵn sàng | TB | Cao | Dùng staging container; chốt checklist hạ tầng và hạn bàn giao; điều chỉnh mốc go-live nếu đầu vào trễ | Nhà trường |
| R05 | 2 | Lộ API key/camera credential | Thấp–TB | Rất cao | Secret manager, least privilege, scan tự động và rotate ngay khi nghi lộ | Developer + admin |
| R06 | 3 | Chưa có consent hợp lệ cho dữ liệu khuôn mặt trẻ em | TB | Rất cao | Không enroll/huấn luyện; dùng dữ liệu giả/được phép; cung cấp phương án điểm danh thay thế | Nhà trường/pháp lý |
| R07 | 3 | Nhận diện khuôn mặt sai trong ánh sáng/góc khó | Cao | Cao | Quality gate, nhiều mẫu hợp lệ, threshold theo FAR/FRR, human review và manual correction | Developer + nhà trường |
| R08 | 3 | Happiness index bị hiểu là đánh giá cá nhân chính thức | TB | Cao | Chỉ hiển thị xu hướng tổng hợp, ghi cảnh báo giới hạn, cấm dùng làm quyết định kỷ luật | Nhà trường |
| R09 | 4 | Dataset xả rác/hút thuốc thiếu tình huống thật | Cao | Cao | Thu thập sớm dữ liệu được phép, hard-negative, shadow mode, hiệu chỉnh rule/presence time | Nhà trường + developer |
| R10 | 4 | Quá nhiều cảnh báo giả | Cao | Cao | ROI, threshold, presence time, debounce, human review; đặt KPI false alerts/camera/giờ | Developer |
| R11 | 5 | Phụ huynh xem nhầm dữ liệu của trẻ khác | Thấp | Rất cao | Authorization ở API, test IDOR, audit, mapping phụ huynh–học sinh được xác minh | Developer |
| R12 | 6 | App Store/Google Play từ chối hoặc xét duyệt lâu | TB | TB–Cao | Chuẩn bị privacy label sớm, submit trước go-live; tạm cung cấp web responsive nếu được duyệt | Nhà trường + developer |
| R13 | 6 | Certificate pinning làm app mất kết nối khi đổi chứng thư | TB | Cao | Thiết kế pin rotation/backup pin, runbook và test trước khi thay cert | Developer + admin |
| R14 | 7 | Luồng camera/API bàn giao trễ hoặc không ổn định | Cao | Cao | Test luồng mẫu sớm; checklist bàn giao; tách lỗi phần mềm và lỗi thiết bị/mạng; dời UAT tương ứng | Đơn vị camera/nhà trường |
| R15 | 7 | 34 luồng vượt năng lực GPU/CPU/storage | TB | Cao | Benchmark tải, tối ưu FPS/resolution theo nghiệp vụ, capacity plan; bổ sung tài nguyên do khách hàng phê duyệt | Developer + nhà trường |
| R16 | 7 | Mất dữ liệu hoặc deploy lỗi | Thấp–TB | Cao | Backup mã hóa, restore/rollback drill, release có version, canary nếu hạ tầng cho phép | Developer |
| R17 | 7–8 | Rò rỉ dữ liệu sinh trắc học/hình ảnh | Thấp | Rất cao | Mã hóa, RBAC/MFA, retention, audit, pentest và IR plan; cô lập/rotate/thông báo theo pháp lý | Hai bên |
| R18 | 8 | Người dùng chưa quen, dùng cảnh báo AI như kết luận cuối | TB | Cao | Đào tạo human-in-the-loop, FAQ, quy trình khiếu nại/chỉnh sửa và review sau vận hành | Nhà trường |
| R19 | 8 | Không rõ trách nhiệm khi có sự cố | TB | Cao | SLA, RACI, contact tree và diễn tập tabletop trước nghiệm thu | Hai bên |

---

# PHẦN 5 — MỐC BÀN GIAO VÀ NGHIỆM THU

| Mốc | Thời điểm dự kiến | Nội dung bàn giao/demo | Tiêu chí nghiệm thu | Bằng chứng |
|---|---:|---|---|---|
| M0 – Kick-off | T0 | Phạm vi, đầu mối, giả định, cách quản lý thay đổi | RACI và lịch phản hồi được xác nhận | Biên bản kick-off |
| M1 – Duyệt thiết kế | Cuối Tuần 2 | SRS, kiến trúc, API/data, UX flow, threat model, consent plan | Không còn yêu cầu quan trọng chưa rõ; ANSCENTER gap có phương án | Biên bản duyệt thiết kế |
| M2 – Backend nền trên staging | Cuối Tuần 5 | Auth, MFA, RBAC, DB, event ingestion, audit, CI/CD | Test API/quyền đạt; secret scan sạch; không còn lỗi High | Test report + demo staging |
| M3 – Demo điểm danh/chấm công | Cuối Tuần 10 | Enrollment có consent, nhận diện, điểm danh, chấm công, chỉ số tổng hợp | Đạt ngưỡng thử nghiệm được duyệt; manual review/audit hoạt động | AI evaluation + demo |
| M4 – Demo AI vi phạm | Cuối Tuần 16 | Đồng phục, bảo hộ, xả rác, hút thuốc trên ANSTS/ANSVIS | Bốn model có model card; test độc lập đạt baseline; rollback được | Model report + video demo |
| M5 – Demo Web Portal | Cuối Tuần 19 | Portal phụ huynh/BGH/GV, review và báo cáo | Dữ liệu đúng; quyền truy cập chéo bị chặn; luồng chính đạt | E2E report + sign-off demo |
| M6 – Mobile UAT build | Cuối Tuần 23 | Bản iOS/Android, push, consent, secure storage | Chạy trên ma trận thiết bị; không lưu token plaintext; hồ sơ store đủ | Build + mobile test report |
| M7 – UAT toàn hệ thống | Cuối Tuần 26 | 34 camera/API, E2E, tải, security, backup/restore | 100% kịch bản critical pass; blocker/critical = 0; High security = 0 | UAT minutes + scan report |
| M8 – Go-live | Tuần 27 | Production release, submit app, monitoring và rollback | Smoke test đạt; dữ liệu/consent đúng; SLA contact hoạt động; không có P1/P2 mở sau hyper-care | Release note + go-live report |
| M9 – Đào tạo và nghiệm thu cuối | Cuối Tuần 29 | Đào tạo, tài liệu, source/artifact theo hợp đồng, runbook, SLA | Đại diện các nhóm hoàn thành đào tạo; checklist bàn giao đủ; lỗi còn lại có kế hoạch được chấp thuận | Biên bản đào tạo + nghiệm thu |
| M10 – Review vận hành | Sau 2–4 tuần vận hành | KPI, cảnh báo giả, sự cố, nhu cầu tinh chỉnh | Hai bên thống nhất backlog và lịch bảo trì/tái huấn luyện | Báo cáo vận hành |

## 5.1 Nguyên tắc xác nhận hoàn thành

- Nghiệm thu căn cứ vào tiêu chí và bằng chứng của từng milestone, không chỉ căn cứ việc “đã demo”.
- Lỗi blocker/critical phải được đóng trước go-live; lỗi nhỏ có thể đưa vào danh sách tồn đọng nếu nhà trường chấp thuận bằng văn bản và không ảnh hưởng an toàn/dữ liệu.
- Độ chính xác AI được đo trên dataset/test window đã thống nhất; không cam kết tuyệt đối 100% trong mọi điều kiện thực tế.
- Chậm do đầu vào A01–A08 chưa được bàn giao sẽ làm dịch chuyển các task phụ thuộc tương ứng. Developer cập nhật lịch và tác động bằng văn bản.
- Mọi thay đổi sau M1 được quản lý qua change request, gồm tác động phạm vi, tiến độ, chi phí và bảo mật.

## 5.2 Hồ sơ bàn giao cuối cùng

1. Tài liệu yêu cầu, kiến trúc, sơ đồ dữ liệu và API contract.
2. Source code/artifact/model/config theo điều khoản sở hữu trí tuệ của hợp đồng.
3. Model card, dataset version metadata, báo cáo đánh giá và hướng dẫn rollback.
4. Hướng dẫn người dùng, hướng dẫn quản trị, runbook triển khai/backup/khôi phục.
5. Threat model, báo cáo scan/pentest, data retention, consent workflow và Incident Response Plan.
6. Release note, known issues, danh mục license/phụ thuộc và lịch bảo trì.
7. Biên bản UAT, đào tạo, go-live và nghiệm thu.

---

**Ghi chú pháp lý:** Hệ thống xử lý dữ liệu cá nhân nhạy cảm và dữ liệu trẻ em. Nhà trường cần có ý kiến của bộ phận pháp lý về consent, thông báo quyền riêng tư, lưu trữ, chia sẻ, xóa và ứng phó rò rỉ trước khi sử dụng dữ liệu thật. Kế hoạch này mô tả yêu cầu kỹ thuật và quy trình quản trị, không thay thế tư vấn pháp lý.
