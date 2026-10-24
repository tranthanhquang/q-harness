# Chuẩn bị public Q-Harness trên GitHub

README và tài liệu đã sẵn trong source; chưa tạo remote, commit, push, tag hay
publish package thay bạn. Repository owner và URL sẽ do bạn chọn trên GitHub.

## 1. Kiểm tra trước khi public

- Đọc [README](../README.md), [LICENSE](../LICENSE) và
  [dependency review](dependency-review.md). MIT áp dụng cho nội dung tự viết;
  không thay license dependency hoặc tài sản của bên thứ ba.
- Chạy các gate trong [CONTRIBUTING](../CONTRIBUTING.md) và kiểm tra package build.
- Giữ nguyên các giới hạn đã ghi trong [verification](verification.md).
  CI chưa chạy trên GitHub không được xem là đã pass trên Linux.
- Kiểm tra không có API key, token, `.env`, dữ liệu khách hàng, private source,
  database dump, artifact riêng hoặc đường dẫn máy cá nhân trong nội dung public.
- Xác nhận bạn có quyền công bố mã nguồn và template. Không đưa template ngoài
  vào MIT nếu chưa có quyền tương ứng.

`.gitignore` loại các file local sau, vẫn giữ chúng trên máy:

- `.env`, `.venv/`, `.python/`, `.tmp/`, `.qharness/`, backups và caches.
- `.agents/`, `.specify/` là cấu hình authoring local của workspace này.
- `Q-Harness_Master_Prompt_SpecKit.md`, `q-harness-session-history.md`, `doc-codex.md`
  là ghi chú đầu vào/phiên làm việc, không thuộc bộ tài liệu public.

`specs/` chứa thiết kế và contract public, được giữ trong repository. `.env.example`
chỉ chứa biến và credential mẫu cho môi trường local. Nếu file nhạy cảm đã được
track trong repository khác, ignore không xóa nó khỏi index/history; phải review
riêng và rotate credential đã lộ. Không dùng `git add -f` để bỏ qua lớp bảo vệ này.

## 2. Tạo repository và review staging

Tại thời điểm chuẩn bị này workspace chưa có `.git`. Khi bạn sẵn sàng, tạo một
repository trống trên GitHub, không sinh README/license khác. Tại checkout root:

```bash
git init -b main
git status --short --untracked-files=all
git add .
git diff --cached --stat
git diff --cached
git ls-files
```

Chỉ chạy `git init` nếu chưa có repository. Review **toàn bộ** danh sách và diff
trước khi commit. Kiểm tra các ghi chú riêng vẫn bị ignore:

```bash
git check-ignore .env .tmp/ .agents/ .specify/ Q-Harness_Master_Prompt_SpecKit.md q-harness-session-history.md doc-codex.md
```

Sau khi tự xác nhận staging an toàn:

```bash
git commit -m "chore: prepare Q-Harness open-source MVP"
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Thay `YOUR_GITHUB_REPOSITORY_URL` bằng URL thật từ trang GitHub **Code**. Nếu đã
có remote, kiểm tra `git remote -v` và dùng remote đúng. Không chép nguyên giá trị
mẫu. Gói tài liệu này không tự thực thi các bước publish trên.

## 3. Thiết lập GitHub sau khi push

1. Kiểm tra workflow **CI** trong tab Actions chạy thành công. Workflow chạy trên
   Ubuntu với Python 3.12, PostgreSQL 18 và Docker sandbox; benchmark lớn tách riêng.
2. Bật private vulnerability reporting để [SECURITY.md](../SECURITY.md) có kênh
   báo lỗi riêng. Bật secret scanning/alerts nếu tài khoản và repository hỗ trợ.
3. Thiết lập bảo vệ nhánh `main`, yêu cầu CI pass và review PR theo quy mô nhóm.
4. Điền description, topics và URL project thật. Chỉ thêm badge khi có URL thật
   và workflow đã chạy; không công bố badge pass giả định.
5. Đọc issue/PR templates, kiểm tra link README trên giao diện GitHub.

Không đặt model API key trong GitHub Actions: bộ test bình thường dùng provider
deterministic, không cần secret này.

## 4. Khi muốn tạo release

- Chốt changelog, version và commit đã kiểm chứng; hiện `0.1.0` chưa được gắn nhãn
  là release đã phát hành.
- Cài thử từ source archive/checkout mới. Review danh sách file wheel/sdist và
  metadata license trước khi attach artifact.
- Với wheel/image có bundled dependency hoặc container, hoàn tất inventory,
  notices và obligations theo [dependency review](dependency-review.md).
  Source công khai không đồng nghĩa binary/container đã được review đầy đủ.
- Ghi rõ native Linux, live provider và human acceptance nào đã chạy hoặc chưa.
  Chỉ thay `NOT_RUN` khi có evidence thật.
- Không upload dữ liệu benchmark lớn, local backup, API key hoặc session notes
  như release asset.
