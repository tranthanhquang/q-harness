# Feature Specification: Q-Harness Platform MVP

**Feature Branch**: `N/A (repository is not initialized with Git)`

**Created**: 2026-10-24

**Status**: Draft — awaiting stakeholder review and approval

**Input**: User description: "Xây dựng Q-Harness từ Q-Harness_Master_Prompt_SpecKit.md và q-harness-session-history.md"

## Vision

Q-Harness giúp một người phát triển quản lý và thực hiện công việc có hỗ trợ AI trên một sản phẩm gồm nhiều repository mà không làm mất ranh giới dự án, quyền truy cập, bằng chứng kiểm thử hoặc nguồn gốc thông tin. Sản phẩm ưu tiên công việc coding, đồng thời tạo nền tảng cho nghiên cứu, tài liệu và workflow nghiệp vụ về sau.

## Clarifications

### Session 2026-10-24

- Q: Trong MVP, cổng dịch vụ mà CLI và Codex dùng để kết nối Q-Harness được phép nhận kết nối từ đâu? → A: Chỉ cùng máy, có token xác thực.
- Q: Khi một coding task chạy qua native Q-Harness runtime, hệ thống nên xin phê duyệt cho thao tác ghi file và chạy lệnh theo cách nào? → A: Duyệt phạm vi task một lần; hỏi lại khi vượt phạm vi.
- Q: Trong MVP, cùng một đường dẫn repository cục bộ có được đăng ký đồng thời vào nhiều Project không? → A: Không; mỗi đường dẫn chỉ thuộc một Project.
- Q: Nếu Q-Harness hoặc worker bị dừng đột ngột giữa một task, MVP phải xử lý execution đang chạy như thế nào? → A: Giữ dữ liệu, đánh dấu gián đoạn, chờ người dùng tiếp tục.
- Q: Nếu một file bị công cụ bên ngoài thay đổi sau khi Q-Harness đọc nhưng trước khi ghi, MVP phải xử lý lần ghi xung đột như thế nào? → A: Chặn ghi, giữ thay đổi mới, chờ người dùng.

## Scope

### MVP Scope

- Quản lý nhiều Project trên một platform; mỗi phiên chỉ có một Project đang hoạt động.
- Mỗi Project có một Harness Workspace và ít nhất hai repository độc lập, kể cả khi các repository không cùng thư mục cha.
- Cung cấp giao diện dòng lệnh native, giao diện dịch vụ có tài liệu và kết nối Codex trong Visual Studio Code qua MCP; các giao diện dùng chung dữ liệu và quy tắc nghiệp vụ, còn giao diện dịch vụ/MCP chỉ nhận kết nối cùng máy bằng token xác thực cục bộ.
- Lập chỉ mục kiến thức ban đầu, tìm kiếm theo từ khóa/symbol, dẫn nguồn, phát hiện dữ liệu cũ và đồng bộ gia tăng.
- Phân loại yêu cầu tự nhiên thành hỏi đáp, thực thi, báo cáo hoặc quản trị; chọn workflow và chính sách tài liệu theo rủi ro.
- Thực hiện một coding workflow Standard có quyền công cụ, approval, retry hữu hạn, kiểm thử thật và lịch sử bất biến.
- Theo dõi work item, task, execution, kết quả kiểm thử, artifact và các sự kiện thông báo tối thiểu.
- Quản lý mẫu báo cáo và tạo ít nhất một báo cáo DOCX cùng một báo cáo XLSX theo hợp đồng `report.md` tương ứng.

### Deferred Scope

- Phase 2: Full SDD end-to-end, checkpoint/resume đầy đủ, semantic knowledge nâng cao, ADR, skill registry nâng cao, watcher/webhook, cross-repo quality gates mở rộng và giao diện web tối thiểu.
- Phase 3: nhiều người dùng và vai trò, multi-agent specialization, distributed workers, remote repository management, object storage, scheduling, thông báo ngoài ứng dụng, document/research agents và vector retrieval khi có bằng chứng giá trị.

### Out of Scope for MVP

- Fork một coding agent lớn làm nền tảng sản phẩm.
- Giao diện web hoàn chỉnh, push email/Telegram hoặc vận hành cloud đa tenant.
- Tự động quét toàn bộ máy, tự triển khai production hoặc thực hiện thao tác phá hủy không có phê duyệt.
- Tự tạo spec/plan/report cho mọi yêu cầu nhỏ hoặc dùng embeddings như điều kiện bắt buộc.
- Chỉnh sửa semantic knowledge quan trọng chỉ từ suy luận không có nguồn kiểm chứng.

## Personas

- **Developer/Operator**: khởi tạo Project, đăng ký repository, hỏi về code, giao việc, duyệt hành động rủi ro và nhận kết quả có bằng chứng.
- **Technical Lead/Reviewer**: theo dõi task, approval, thay đổi đa repository, quality gates và trạng thái hoàn tất.
- **Report Consumer**: yêu cầu và đọc artifact theo mẫu mà không cần biết cách hệ thống thu thập dữ liệu.
- **Codex Client**: tác nhân bên ngoài dùng các capability được cấp quyền; không thay thế native Q-Harness runtime.
- **Automation Client**: công cụ được cấp quyền gọi giao diện dịch vụ để tích hợp Q-Harness vào workflow khác.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create an Isolated Multi-Repository Project (Priority: P1)

Là Developer, tôi muốn đăng ký một Project gồm nhiều repository và chuyển ngữ cảnh Project có kiểm soát để Harness luôn thao tác đúng sản phẩm.

**Why this priority**: Project boundary là nền tảng cho mọi capability khác và ngăn dữ liệu hoặc thao tác đi nhầm dự án.

**Independent Test**: Tạo Project A với hai repository độc lập và Project B với một repository, chuyển qua lại giữa hai Project rồi xác nhận danh sách, trạng thái và dữ liệu mỗi Project không lẫn nhau.

**Acceptance Scenarios**:

1. **Given** hai repository hợp lệ ở các đường dẫn đã được cho phép, **When** người dùng khởi tạo Project A và đăng ký cả hai, **Then** Project A có stable ID, workspace riêng, vai trò repository và trạng thái Git độc lập cho từng repository.
2. **Given** Project A và Project B đã đăng ký, **When** người dùng chọn Project A từ một thư mục thuộc Project A, **Then** Harness xác định đúng Project mà không quét các đường dẫn ngoài phạm vi cho phép.
3. **Given** một đường dẫn thoát khỏi phạm vi Project qua path traversal hoặc symlink, **When** người dùng hoặc công cụ yêu cầu truy cập, **Then** Harness từ chối và ghi lại sự kiện an toàn mà không đọc nội dung đích.
4. **Given** một đường dẫn repository đã thuộc Project A, **When** người dùng đăng ký đúng đường dẫn đó vào Project B, **Then** Harness từ chối và hướng dẫn dùng một checkout riêng nếu hai Project cần cùng source.

---

### User Story 2 - Build and Refresh Trusted Project Knowledge (Priority: P1)

Là Developer, tôi muốn lập chỉ mục và tìm kiếm kiến thức có dẫn nguồn trên toàn bộ repository của Project để nhận đúng context mà không nạp toàn bộ codebase.

**Why this priority**: Context có nguồn và còn mới là điều kiện để hỏi đáp và coding workflow đáng tin cậy.

**Independent Test**: Lập chỉ mục Project A, tìm một file và symbol, sửa một file rồi refresh; kết quả mới phải xuất hiện qua đồng bộ gia tăng trong khi Project B không thể truy cập dữ liệu Project A.

**Acceptance Scenarios**:

1. **Given** Project A có hai repository đã đăng ký, **When** người dùng yêu cầu index, **Then** Harness khám phá các nguồn được phép và trả kết quả tìm kiếm kèm repository, đường dẫn, dòng hoặc symbol, cùng phiên bản branch/commit khi có.
2. **Given** một file đã index được thay đổi bởi Harness, **When** execution kết thúc dù thành công, thất bại hay bị hủy, **Then** phần index liên quan được đồng bộ hoặc được đánh dấu stale rõ ràng.
3. **Given** một file được sửa ngoài Harness, **When** người dùng tìm kiếm hoặc bắt đầu task tiếp theo, **Then** Harness kiểm tra freshness và không âm thầm trả dữ liệu cũ.
4. **Given** nguồn chứa secret, binary, build output hoặc file bị loại trừ, **When** index chạy, **Then** nội dung đó không được lưu vào knowledge hoặc log.

---

### User Story 3 - Execute a Verifiable Coding Task (Priority: P1)

Là Developer, tôi muốn mô tả bug hoặc task bằng ngôn ngữ tự nhiên và nhận thay đổi tối thiểu đã được kiểm thử để không phải nhớ keyword hay tự ghép lịch sử thực thi.

**Why this priority**: Đây là giá trị coding cốt lõi của MVP và chứng minh Harness quản lý trọn vẹn một execution.

**Independent Test**: Giao một task nhỏ thay đổi hai repository, cho phép các công cụ cần thiết, chạy test riêng và test hợp đồng, rồi kiểm tra task chỉ hoàn tất khi mọi gate bắt buộc đạt.

**Acceptance Scenarios**:

1. **Given** một yêu cầu tự nhiên, **When** Harness phân tích yêu cầu, **Then** nó hiển thị ngắn gọn intent, loại work item, mức rủi ro, workflow, tài liệu dự kiến và yêu cầu kiểm chứng trước khi hành động đáng kể.
2. **Given** task ảnh hưởng hai repository, **When** workflow chạy, **Then** cùng một Task ID liên kết từng repository, branch/commit, thay đổi và kết quả test độc lập mà không giả định một commit chung.
3. **Given** code đã thay đổi nhưng test bắt buộc thất bại, **When** retry hữu hạn kết thúc, **Then** task không ở trạng thái COMPLETED và người dùng thấy lỗi, bằng chứng test cùng bước tiếp theo.
4. **Given** người dùng đã duyệt phạm vi đường dẫn, công cụ và lệnh cho một task, **When** runtime thực hiện action nằm trong phạm vi đó, **Then** action không yêu cầu duyệt lại; nếu action mở rộng đường dẫn, quyền, network, credential hoặc mức rủi ro, runtime phải dừng và xin phê duyệt mới.
5. **Given** feature lớn hoặc thay đổi kiến trúc, **When** Harness chọn Full SDD, **Then** workflow dừng tại SPEC_READY để người dùng review/approve trước plan hoặc implementation.
6. **Given** một file đã đổi ngoài Harness kể từ lần runtime đọc gần nhất, **When** runtime chuẩn bị ghi file đó, **Then** lần ghi bị từ chối, thay đổi mới được giữ nguyên, task chuyển BLOCKED và người dùng được yêu cầu quyết định bước tiếp theo.

---

### User Story 4 - Ask Safely from Supported Interfaces (Priority: P2)

Là Developer dùng terminal, một automation client hoặc Codex trong Visual Studio Code, tôi muốn hỏi về Project và xem trạng thái task/report qua cùng một nguồn dữ liệu mà không cho phép câu hỏi làm thay đổi workspace.

**Why this priority**: Hỏi đáp an toàn đem lại giá trị hằng ngày và chứng minh ranh giới giữa Codex client với native runtime.

**Independent Test**: Gửi cùng một câu hỏi qua giao diện native, giao diện dịch vụ và Codex connector, so sánh nguồn dẫn, rồi thử ép `/ask` gọi công cụ ghi để xác nhận yêu cầu bị chặn.

**Acceptance Scenarios**:

1. **Given** Project đang hoạt động và knowledge còn mới, **When** người dùng gửi `/ask`, **Then** câu trả lời ngắn gọn, có nguồn/caveat cần thiết và không tạo task, tài liệu hoặc báo cáo tự động.
2. **Given** nội dung `/ask` yêu cầu sửa file hoặc chạy write tool, **When** Harness xử lý, **Then** quyền read-only chặn thao tác thay vì chỉ dựa vào hướng dẫn ngôn ngữ.
3. **Given** Codex đã được xác thực và cấp scope Project A, **When** Codex tìm knowledge hoặc xem task/report, **Then** kết quả giống nguồn dữ liệu native và không lộ dữ liệu Project B.
4. **Given** Codex yêu cầu action ghi hoặc chạy, **When** action cần quyền cao hơn scope hiện tại, **Then** Harness yêu cầu permission/approval phù hợp hoặc từ chối.
5. **Given** một automation client được xác thực với cùng Project scope, **When** client gọi capability tương đương CLI, **Then** business decision, permission và trạng thái kết quả nhất quán giữa các giao diện.
6. **Given** kết nối không xuất phát từ cùng máy hoặc thiếu token cục bộ hợp lệ, **When** giao diện dịch vụ hoặc MCP nhận yêu cầu, **Then** yêu cầu bị từ chối trước khi đọc dữ liệu Project.

---

### User Story 5 - Generate a Report from a Governed Template (Priority: P2)

Là Report Consumer, tôi muốn yêu cầu báo cáo theo template đã đăng ký để nhận file đúng cấu trúc, có nguồn dữ liệu và không chứa số liệu bịa đặt.

**Why this priority**: Báo cáo theo mẫu là capability khác biệt của Q-Harness và dùng lại lịch sử execution đã thu thập.

**Independent Test**: Với dữ liệu fixture, tạo báo cáo tiến độ DOCX và kết quả kiểm thử XLSX, rồi xác nhận mỗi artifact mở được, đủ section/field, đúng phiên bản template và xử lý đúng dữ liệu thiếu.

**Acceptance Scenarios**:

1. **Given** nhiều template đã đăng ký, **When** người dùng yêu cầu danh sách, **Then** Harness hiển thị ID, phiên bản, output hỗ trợ, scope và quyền cần thiết.
2. **Given** yêu cầu một report cụ thể, **When** generation bắt đầu, **Then** Harness đọc `report.md` tương ứng trước, kiểm tra template và chỉ thu thập nguồn được cấp quyền.
3. **Given** thiếu dữ liệu bắt buộc, **When** report contract yêu cầu hỏi hoặc đánh dấu Missing/N/A, **Then** Harness làm đúng policy đó và không bịa giá trị.
4. **Given** artifact không mở được hoặc sai section, field, style hay công thức bắt buộc, **When** validation chạy, **Then** report không chuyển sang READY.
5. **Given** validation thành công, **When** artifact được lưu, **Then** Harness phát sự kiện REPORT_READY với đường dẫn, template version và data provenance; trạng thái VIEWED không được coi là APPROVED.

---

### User Story 6 - Inspect Auditable Progress (Priority: P3)

Là Technical Lead, tôi muốn xem task, execution, approval, test và notification events để biết chính xác việc gì đã xảy ra và vì sao một task hoàn tất hoặc bị chặn.

**Why this priority**: Auditability cần cho độ tin cậy nhưng phụ thuộc vào các luồng MVP phía trên tạo dữ liệu.

**Independent Test**: Chạy một execution thành công, một execution test fail và một execution bị hủy; truy vấn timeline phải phản ánh đúng trạng thái, bằng chứng và liên kết artifact của từng lần chạy.

**Acceptance Scenarios**:

1. **Given** một task có nhiều execution, **When** reviewer xem lịch sử, **Then** từng execution có thời gian, Project/repository context, intent, workflow, tool activity đã redact, thay đổi, test, approval, lỗi và artifact liên quan.
2. **Given** task chuyển trạng thái, **When** sự kiện được ghi, **Then** transition không hợp lệ bị từ chối và log lịch sử trước đó không bị sửa.
3. **Given** có SPEC_READY, APPROVAL_REQUIRED, TASK_BLOCKED, TEST_FAILED, TASK_COMPLETED hoặc REPORT_READY, **When** người dùng truy vấn notification, **Then** sự kiện hiển thị đúng đối tượng, thời điểm và trạng thái hiện hành.
4. **Given** runtime hoặc worker dừng đột ngột giữa task, **When** Q-Harness khởi động lại, **Then** source và log đã có được giữ nguyên, execution là INTERRUPTED, task là BLOCKED, knowledge được đồng bộ hoặc đánh dấu stale và không action nào tự tiếp tục trước xác nhận của người dùng.

### Edge Cases

- Repository đã đăng ký bị di chuyển, mất quyền đọc hoặc không còn là Git repository.
- Hai Project cần cùng source; mỗi Project phải dùng một checkout ở đường dẫn riêng, không được đăng ký chung một đường dẫn cục bộ.
- Repository ở detached HEAD, có thay đổi chưa commit hoặc branch đổi trong lúc index; nếu file đổi ngoài Harness giữa lần đọc và ghi, lần ghi phải bị chặn thay vì auto-merge hoặc ghi đè.
- Execution bị hủy hoặc worker dừng sau khi đã sửa file nhưng trước khi chạy test/sync; hệ thống phải giữ dữ liệu, ghi nhận gián đoạn, xử lý freshness và chờ người dùng quyết định bước tiếp theo.
- Một file rất lớn, encoding không hỗ trợ, generated file, binary, symlink loop hoặc đường dẫn trỏ ra ngoài allowed roots.
- Truy vấn không có kết quả, nguồn dẫn không còn tồn tại hoặc semantic knowledge mâu thuẫn với source knowledge mới hơn.
- Intent classifier có độ tin cậy thấp cho yêu cầu có thể gây thay đổi lớn; hệ thống phải yêu cầu xác nhận thay vì tự chạy.
- Cùng một tool invocation hoặc report request được gửi lặp lại sau timeout; không được tạo tác dụng phụ trùng lặp ngoài policy.
- Template trùng ID, sai phiên bản, checksum thay đổi, không đọc được, thiếu `report.md` hoặc yêu cầu output không hỗ trợ.
- Dữ liệu report đến từ nhiều execution với trạng thái xung đột; provenance và missing-data policy phải được giữ nguyên.
- Test không thể chạy do môi trường thiếu dependency; kết quả phải là NOT_RUN/BLOCKED phù hợp, không phải verified.
- Mất kết nối đến model hoặc service phụ trợ; workspace và lịch sử đã ghi không được hỏng hoặc bị báo hoàn tất sai.

## Requirements *(mandatory)*

### Functional Requirements

#### Project and Workspace

- **FR-001 [MUST]**: Hệ thống MUST quản lý nhiều Project, mỗi Project có stable ID, tên, cấu hình, workspace, repository, knowledge, work item, task, execution, artifact và report template riêng.
- **FR-002 [MUST]**: Hệ thống MUST cho phép khởi tạo, đăng ký, liệt kê, chọn, xem trạng thái, index và refresh một Project mà không quét đường dẫn chưa được đăng ký.
- **FR-003 [MUST]**: Một Project MUST hỗ trợ nhiều repository độc lập có role, path, quyền và Git metadata riêng, kể cả khi không cùng thư mục cha; một đường dẫn repository cục bộ MUST chỉ được đăng ký cho một Project, còn cùng source MAY được checkout ở đường dẫn riêng cho Project khác.
- **FR-004 [MUST]**: Mỗi phiên làm việc MUST chỉ có một Project context hiện hành; chuyển Project MUST cập nhật toàn bộ phạm vi knowledge, tool và execution.
- **FR-005 [MUST]**: Hệ thống MUST ngăn path traversal, symlink escape và truy cập chéo Project; mọi từ chối MUST không làm lộ nội dung đích.
- **FR-006 [MUST]**: Cấu hình có thể version-control MUST tách khỏi index, cache, artifact nhạy cảm và secret không được commit.

#### Knowledge

- **FR-007 [MUST]**: Hệ thống MUST index các nguồn được phép gồm cấu trúc repository, hướng dẫn dự án, manifest, file, symbol, dependency, route và schema/migration có thể nhận diện.
- **FR-008 [MUST]**: Hệ thống MUST cung cấp lexical và symbol search với provenance gồm Project, repository, đường dẫn, dòng hoặc symbol, thời điểm index và branch/commit khi có.
- **FR-009 [MUST]**: Hệ thống MUST truy xuất context theo task và phạm vi cần thiết thay vì đưa toàn bộ Project vào một yêu cầu model.
- **FR-010 [MUST]**: Hệ thống MUST phân biệt source knowledge do máy trích xuất với semantic knowledge; semantic knowledge quan trọng MUST không bị ghi đè chỉ từ suy luận chưa kiểm chứng.
- **FR-011 [MUST]**: Sau mọi execution có thay đổi source, hệ thống MUST đồng bộ gia tăng phần bị ảnh hưởng hoặc đánh dấu index stale, không phụ thuộc execution thành công hay thất bại.
- **FR-012 [MUST]**: Trước khi dùng knowledge cho search hoặc task, hệ thống MUST phát hiện thay đổi ngoài Harness bằng trạng thái nguồn hiện tại và MUST không âm thầm dùng index cũ.
- **FR-013 [MUST]**: Người dùng MUST có thể yêu cầu full reindex; hệ thống SHOULD chỉ tự full reindex khi khởi tạo, đổi cấu trúc lớn hoặc đổi schema index.
- **FR-014 [MUST]**: Hệ thống MUST loại trừ secret, credential, file môi trường, vùng Git nội bộ, dependency/build output, binary và file vượt giới hạn được công bố khỏi index và log.

#### Intent, Workflow, and Runtime

- **FR-015 [MUST]**: Hệ thống MUST nhận yêu cầu ngôn ngữ tự nhiên mà không bắt keyword cho bug, feature, refactor hoặc chore; `/ask` và `/report` MUST được hỗ trợ như shortcut rõ nghĩa.
- **FR-016 [MUST]**: Mỗi yêu cầu MUST được biểu diễn độc lập theo intent, work item type, tracking mode, risk/complexity, workflow, documentation mode, verification requirement và report policy.
- **FR-017 [MUST]**: Khi classification không chắc chắn và hành động có thể gây thay đổi lớn, hệ thống MUST yêu cầu xác nhận trước khi chạy.
- **FR-018 [MUST]**: MVP MUST cung cấp một coding workflow Standard từ phân tích đến thay đổi, kiểm thử, review, verification và kết quả; retry MUST hữu hạn và có thể hủy; execution bị dừng đột ngột MUST không tự động resume hoặc rollback.
- **FR-019 [MUST]**: `/ask` MUST được enforce read-only bằng quyền công cụ, trả lời ngắn gọn có nguồn/caveat và MUST NOT tự tạo task, tài liệu hay report.
- **FR-020 [MUST]**: Hệ thống MUST áp dụng adaptive document policy: không mặc định tạo Spec Kit artifacts cho ask/bug nhỏ/task nhỏ, và chọn Full SDD cùng approval gate cho feature lớn hoặc thay đổi kiến trúc.
- **FR-021 [MUST]**: Native runtime MUST xin phê duyệt một lần cho phạm vi đường dẫn, công cụ và lệnh của task; action trong phạm vi đã duyệt không hỏi lại, còn action mở rộng đường dẫn, quyền, network, credential hoặc mức rủi ro MUST dừng để xin phê duyệt mới và mọi action MUST được audit.
- **FR-022 [MUST]**: Execution MUST chạy trong phạm vi Project được cách ly với giới hạn tài nguyên, thời gian, network, file và credential; unrestricted host access MUST NOT là mặc định.
- **FR-023 [MUST]**: Mọi code change MUST có quality gates phù hợp; trước mỗi lần ghi, runtime MUST phát hiện file đã đổi kể từ lần đọc gần nhất, từ chối ghi xung đột, giữ thay đổi mới và chuyển task sang BLOCKED chờ người dùng; task MUST NOT hoàn tất nếu test bắt buộc fail hoặc không chạy, và kết quả thực MUST được giữ làm bằng chứng.
- **FR-024 [MUST]**: Một Task ID MUST có thể liên kết nhiều repository, execution, branch/commit, pull request và test run mà không gộp Git lifecycle của các repository.
- **FR-025 [SHOULD]**: Tool invocation có thể lặp lại SHOULD dùng idempotency key hoặc cơ chế tương đương khi tác dụng phụ có thể bị nhân đôi.

#### Records, Notifications, and Interfaces

- **FR-026 [MUST]**: Hệ thống MUST tách WorkItem, Task, Execution, Artifact và Report thành các bản ghi có ID ổn định và quan hệ truy vết được.
- **FR-027 [MUST]**: Task MUST hỗ trợ CREATED, ANALYZING, WAITING_APPROVAL, PLANNING, IMPLEMENTING, TESTING, REVIEWING, BLOCKED, FAILED, COMPLETED và CANCELLED; transition không hợp lệ MUST bị từ chối.
- **FR-028 [MUST]**: Execution history MUST ghi thời gian, Project/repository/branch/commit, intent, workflow, tool activity đã redact, diff metadata, test outcome, failure, approval, artifact reference và usage/cost khi đo được; sau dừng đột ngột, source/log MUST được giữ, execution MUST là INTERRUPTED, task MUST là BLOCKED, knowledge MUST được đồng bộ hoặc đánh dấu stale và recovery MUST chờ xác nhận người dùng.
- **FR-029 [MUST]**: Hệ thống MUST phát và cho phép truy vấn SPEC_READY, APPROVAL_REQUIRED, TASK_BLOCKED, TEST_FAILED, TASK_COMPLETED và REPORT_READY; không hứa push nền khi không có service đang chạy.
- **FR-030 [MUST]**: CLI, giao diện dịch vụ, native runtime và Codex connector MUST dùng chung application state và business rules; kết nối Codex MUST không được coi là native Q-Harness agent loop.
- **FR-031 [MUST]**: Giao diện dịch vụ và MCP MUST chỉ nhận kết nối cùng máy, yêu cầu token xác thực cục bộ, giới hạn scope theo Project và chỉ cho phép action ghi/chạy khi permission cùng approval policy cho phép.

#### Reports and Skills

- **FR-032 [MUST]**: Report Registry MUST quản lý template ID, semantic version, schema, output hỗ trợ, checksum, scope, quyền và metadata preview/list/select.
- **FR-033 [MUST]**: Mỗi loại report MUST có `report.md` quy định section, field, data source, format, validation, missing-data policy và ngôn ngữ; file template MUST quyết định presentation thực tế.
- **FR-034 [MUST]**: Trước khi tạo report, hệ thống MUST resolve đúng template, đọc `report.md`, validate contract/template và chỉ thu thập dữ liệu được cấp quyền.
- **FR-035 [MUST]**: Report generation MUST không suy đoán số liệu thiếu; hệ thống MUST hỏi hoặc ghi Missing/N/A đúng theo contract và giữ section bắt buộc.
- **FR-036 [MUST]**: MVP MUST tạo và validate ít nhất một report tiến độ dạng DOCX và một report kết quả test dạng XLSX; artifact lỗi nội dung, cấu trúc, định dạng, công thức hoặc openability MUST không được READY.
- **FR-037 [MUST]**: Report READY MUST lưu template version, checksum và data provenance; report state MUST tách PENDING, GENERATING, READY và VIEWED, trong đó VIEWED không đồng nghĩa APPROVED.
- **FR-038 [MUST]**: Skill Registry MUST chỉ coi một skill là khả dụng sau khi xác minh nguồn/path, version, license, quyền, script và kiểm thử tích hợp phù hợp; nội dung skill MUST được xem là đầu vào không tin cậy theo mặc định.
- **FR-039 [MUST]**: Caveman-style brevity MUST chỉ áp dụng cho `/ask` và giải thích ngắn, không áp dụng cho code, spec, test, report hay log kiểm thử.
- **FR-040 [COULD]**: MVP COULD ghi usage/cost khi nguồn dữ liệu cung cấp số đo đáng tin cậy; thiếu số đo MUST được thể hiện là không có dữ liệu thay vì ước lượng.
- **FR-041 [MUST]**: MVP MUST có tài liệu local gồm hướng dẫn cài/chạy, cấu hình mẫu, Project mẫu nhiều repository, command/capability reference, cách chạy kiểm thử và troubleshooting; tài liệu MUST chỉ dẫn các dependency môi trường thực sự cần thiết.

### Non-Functional Requirements

- **NFR-001 Security & Isolation**: Mọi trust boundary phải dùng deny-by-default, least privilege, secret redaction và project-scoped authorization; kiểm thử phải chứng minh không đọc/index/log dữ liệu ngoài allowed paths.
- **NFR-002 Reliability**: State transition, approval, artifact publication và knowledge freshness phải nhất quán khi execution thành công, thất bại, timeout hoặc bị hủy; không được báo thành công sai.
- **NFR-003 Auditability**: Event history đã ghi phải bất biến đối với thao tác thông thường và đủ dữ kiện để reviewer tái dựng quyết định, nguồn, thay đổi và kết quả kiểm thử.
- **NFR-004 Performance**: Trên bộ Project chuẩn của MVP, 95% thao tác list/status và knowledge query phải hiển thị kết quả trong 3 giây; incremental refresh một file phải hoàn tất hoặc báo stale trong 30 giây.
- **NFR-005 Scalability Boundary**: MVP phải vận hành đúng với ít nhất 10 Project, 20 repository mỗi Project và 100.000 file được phép mỗi Project mà vẫn giữ đúng isolation; benchmark chi tiết được chốt ở plan.
- **NFR-006 Usability**: Một developer quen terminal phải hoàn tất init, thêm hai repository, index và chạy truy vấn đầu tiên trong 10 phút bằng tài liệu local, không cần giao diện web.
- **NFR-007 Observability**: Mọi request/execution phải có correlation identity và trạng thái có thể truy vấn; log phải có cấu trúc, đủ chẩn đoán và không chứa secret.
- **NFR-008 Maintainability**: Capability chung phải có một nguồn business logic cho các giao diện; dependency bên ngoài phải được đánh giá license, version compatibility và khả năng thay thế trước khi chốt ở plan.
- **NFR-009 Cost Control**: Context gửi tới model phải giới hạn theo task, có budget và bounded retries; hệ thống không được dùng full-project context khi retrieval hẹp đáp ứng yêu cầu.
- **NFR-010 Compatibility**: Repository giữ Git lifecycle độc lập và cấu hình versioned phải có đường nâng cấp có thể đảo ngược khi schema thay đổi.

### Requirement Acceptance Mapping

| Requirement Area | Primary Acceptance Evidence |
|------------------|-----------------------------|
| FR-001–FR-006 | User Story 1 scenarios and cross-project isolation tests |
| FR-007–FR-014 | User Story 2 scenarios, freshness tests and exclusion tests |
| FR-015–FR-025 | User Story 3 and 4 scenarios, permission tests and real test logs |
| FR-026–FR-031, FR-041 | User Story 4 and 6 scenarios, state transition and interface contract tests, plus a clean-environment documentation walkthrough |
| FR-032–FR-040 | User Story 5 scenarios, generated artifact fixtures and skill trust checks |
| NFR-001–NFR-010 | Security, recovery, load, usability and traceability acceptance suites |

### Key Entities

- **Platform**: Shared control plane quản lý nhiều Project nhưng không trộn Project context.
- **Project**: Một sản phẩm/hệ thống nghiệp vụ có stable ID, cấu hình, một Harness Workspace và nhiều repository.
- **Harness Workspace**: Ranh giới logic chứa cấu hình, knowledge, quyền, task, execution, artifact và report templates của một Project.
- **Repository**: Một Git lifecycle độc lập, có role, path/remote reference, allowed scope, branch/commit và trạng thái.
- **Knowledge Entry**: Thông tin source hoặc semantic có provenance, hash, thời điểm index, repository, branch/commit, confidence và trạng thái freshness/invalidation.
- **WorkItem**: Yêu cầu nghiệp vụ được phân loại như bug, feature, refactor, chore, research, document hoặc other.
- **Task**: Đơn vị theo dõi có stable ID, workflow, risk, trạng thái, approval và liên kết nhiều repository/execution.
- **Execution**: Một lần chạy task, chứa checkpoint, tool activity, thay đổi, test evidence và outcome như thành công, thất bại, hủy hoặc INTERRUPTED.
- **Tool Permission**: Quyền theo action, Project và task scope đã duyệt, gồm risk, timeout, network/file/credential scope cùng điều kiện phải xin phê duyệt lại.
- **Artifact**: File đầu ra có loại, checksum, provenance, quyền và liên kết task/execution.
- **Report Template**: Contract `report.md`, presentation template/assets, ID, version, schema, output formats, scope và quyền.
- **Report**: Artifact được tạo từ một Report Template cùng data provenance và validation result.
- **Skill**: Gói hướng dẫn/tài nguyên đã được xác minh về nguồn, version, license và quyền trước khi dùng.
- **Event/Notification**: Bản ghi bất biến về state transition hoặc mốc cần người dùng chú ý.

### State Models

- **Task**: `CREATED → ANALYZING → [WAITING_APPROVAL] → PLANNING → IMPLEMENTING → TESTING → REVIEWING → COMPLETED`; từ các trạng thái đang chạy có thể sang `BLOCKED`, `FAILED` hoặc `CANCELLED`; execution bị gián đoạn hoặc ghi file xung đột đưa task sang `BLOCKED` và chỉ tiếp tục sau xác nhận người dùng.
- **Report**: `PENDING → GENERATING → READY → VIEWED`; generation/validation thất bại giữ lỗi có thể truy vấn và không đi vào READY; VIEWED không tạo approval.
- **Knowledge**: `UNINDEXED → INDEXING → FRESH`; thay đổi nguồn chuyển entry liên quan sang `STALE`, sau refresh trở lại `FRESH`; lỗi index vẫn giữ trạng thái cũ rõ ràng thay vì giả định fresh.
- **Approval**: `REQUESTED → APPROVED | REJECTED | EXPIRED | CANCELLED`; action bị gate chỉ được chạy từ APPROVED và trong đúng scope đã duyệt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% acceptance suite chứng minh Project A không thể search, index, đọc hoặc dùng tool trên dữ liệu chỉ thuộc Project B, kể cả qua path traversal và symlink; 100% đăng ký trùng cùng đường dẫn repository giữa hai Project bị từ chối.
- **SC-002**: Một developer mới có thể tạo Project với hai repository, index và nhận kết quả có nguồn đầu tiên trong tối đa 10 phút theo tài liệu local.
- **SC-003**: Trên bộ Project chuẩn, ít nhất 95% truy vấn knowledge hiển thị kết quả hoặc thông báo freshness có thể hành động trong 3 giây.
- **SC-004**: Sau khi một file được thay đổi, kết quả mới xuất hiện qua incremental refresh hoặc trạng thái stale được hiển thị trong tối đa 30 giây mà không cần full reindex.
- **SC-005**: 100% `/ask` security tests không tạo file, task, report hoặc write-tool side effect và câu trả lời giữ nguồn/caveat bắt buộc.
- **SC-006**: 100% task có code change không thể chuyển COMPLETED khi test bắt buộc fail hoặc NOT_RUN; reviewer truy xuất được test evidence thực tế.
- **SC-007**: Một task mẫu thay đổi hai repository giữ đúng một Task ID, Git/test evidence riêng từng repository và vượt qua contract/integration acceptance test.
- **SC-008**: Giao diện dịch vụ và Codex trong Visual Studio Code hoàn tất 100% acceptance tests cho project info, knowledge search, task status và report list/generate theo đúng scope/approval; 100% kết nối ngoài máy hoặc thiếu token hợp lệ bị từ chối trước khi đọc dữ liệu Project.
- **SC-009**: 100% artifact DOCX và XLSX trong acceptance suite mở được, đủ section/field bắt buộc, đúng template version/checksum, giữ provenance và không có dữ liệu tự suy đoán.
- **SC-010**: Ít nhất 90% người dùng thử nghiệm hoàn tất luồng init → ask → task status → report list ngay lần đầu mà không cần hỗ trợ trực tiếp.
- **SC-011**: Với execution thành công, test fail, bị hủy và bị dừng đột ngột, 100% timeline audit thể hiện đúng outcome, task state, approval, tool activity đã redact, thay đổi, test, freshness và artifact liên quan; không execution gián đoạn nào tự resume hoặc rollback.
- **SC-012**: MVP chứng minh vận hành đúng và không lẫn dữ liệu với ít nhất 10 Project, 20 repository mỗi Project và 100.000 file được phép mỗi Project trong acceptance environment.
- **SC-013**: Trên môi trường local sạch đáp ứng prerequisite đã công bố, một reviewer hoàn tất walkthrough cài/chạy, Project mẫu, kiểm thử và troubleshooting chỉ bằng tài liệu MVP mà không gặp bước thiếu hoặc lệnh không còn hợp lệ.
- **SC-014**: Trong acceptance task, 100% action thuộc phạm vi đã duyệt chạy không hỏi lại và 100% action mở rộng đường dẫn, quyền, network, credential hoặc mức rủi ro bị chặn cho tới khi có phê duyệt mới.
- **SC-015**: Trong 100% acceptance tests nơi file đổi ngoài Harness giữa lần đọc và ghi, runtime không ghi đè hoặc auto-merge, giữ nguyên thay đổi mới, chuyển task sang BLOCKED và cung cấp thông tin xung đột cho người dùng.

## Assumptions

- MVP chạy local-first cho một operator tin cậy trên máy phát triển; multi-user RBAC và remote hosted operation được hoãn.
- Người dùng chủ động đăng ký Project và repository, có quyền hợp pháp với các đường dẫn/nội dung đó, và Git đã có cho các repository cần metadata.
- Mỗi đường dẫn repository cục bộ thuộc đúng một Project; nhu cầu dùng cùng source cho Project khác được đáp ứng bằng checkout riêng.
- Native CLI là giao diện quản trị chính; Codex trong Visual Studio Code là client qua MCP, còn dashboard web được hoãn.
- Giao diện dịch vụ và MCP của MVP chỉ phục vụ client trên cùng máy và luôn yêu cầu token xác thực cục bộ.
- Action đọc được cấp theo Project; action ghi, command execution, network hoặc truy cập credential cần quyền rõ ràng và approval theo rủi ro.
- Một approval của native runtime chỉ có hiệu lực trong phạm vi task đã trình bày; thay đổi ngoài phạm vi đó luôn cần approval mới.
- Provider/model cụ thể, dependency và topology triển khai là quyết định của phase architecture/plan; spec chỉ yêu cầu không hardcode credential/model và có thể thay thế provider.
- MVP cung cấp một template tiến độ DOCX và một template kết quả kiểm thử XLSX làm mẫu chấp nhận; PDF là output về sau hoặc chỉ được bật khi có pipeline/template được kiểm chứng.
- Manual refresh và freshness check trước khi dùng knowledge là đủ cho MVP; watcher, Git hook và CI webhook thuộc Phase 2.
- MVP không tự merge hoặc ghi đè file đã đổi ngoài Harness kể từ lần đọc gần nhất; người dùng quyết định cách tiếp tục sau khi task bị chặn.
- Source knowledge là nguồn ưu tiên khi mâu thuẫn với semantic summary; cập nhật business rule/architecture quan trọng cần nguồn hoặc review con người.
- Dữ liệu lớn, cache, index, secret và generated artifact không được version-control; chỉ cấu hình và report contracts/templates được phê duyệt mới có thể commit.
- Constitution hiện tại chỉ là template chưa được ratify nên không thêm ràng buộc dự án ngoài những nguyên tắc đã nêu trong hai tài liệu đầu vào.

## Dependencies

- Một môi trường local có thể thực thi worker cách ly và chạy tool/test của các repository mẫu.
- Ít nhất hai repository thử nghiệm độc lập cùng fixtures cho thay đổi code, knowledge refresh và contract tests.
- Codex client có khả năng kết nối MCP để chạy connector acceptance test.
- Hai report contracts cùng template DOCX/XLSX hợp lệ và bộ dữ liệu fixture có cả trường hợp đầy đủ lẫn thiếu dữ liệu.
- Quyết định kiến trúc được người dùng review và approve trước khi triển khai phần lớn hệ thống.

## Glossary

- **One Project = One Harness Workspace = Many Repositories**: một Project là ranh giới nghiệp vụ/kiến thức/quyền; không đồng nghĩa một Git repository hay một server riêng.
- **Native Runtime**: agent loop do Q-Harness điều phối trực tiếp.
- **Codex-as-client**: Codex gọi capability Q-Harness qua MCP nhưng vẫn giữ agent loop riêng.
- **Source Knowledge**: dữ liệu trích xuất từ source với provenance và freshness.
- **Semantic Knowledge**: overview, architecture, business rule hoặc ADR có diễn giải và cần kiểm chứng.
- **Freshness**: mức độ index phản ánh trạng thái nguồn hiện tại.
- **Adaptive Document Policy**: chỉ tạo artifact mô tả khi độ phức tạp/rủi ro hoặc yêu cầu người dùng làm nó cần thiết.
- **Report Contract**: file `report.md` bắt buộc quy định nội dung, nguồn, định dạng và validation cho một loại báo cáo.
- **Approval Gate**: điểm dừng bắt buộc trước action vượt quyền/rủi ro hoặc trước bước lớn trong Full SDD.

