# Cài đặt Q-Harness

Hướng dẫn cài từ source cho macOS/Linux. Chạy các lệnh trong thư mục gốc của
checkout, dùng bash hoặc zsh. Phiên bản hiện tại: MVP 0.1.0, Python 3.12.
Chưa có hướng dẫn cài từ PyPI hoặc ứng dụng desktop/web.

## 1. Cần chuẩn bị gì?

| Thành phần | Mục đích |
|------------|----------|
| Python 3.12 và module `venv` | Chạy CLI, HTTP/MCP và worker |
| Git và ripgrep (`rg`) | Quản lý, tìm kiếm source |
| Docker đang chạy, Compose v2 | PostgreSQL và sandbox thực thi test/report |
| PostgreSQL 18 | Metadata; có thể dùng container trong `compose.yaml` |
| Client PostgreSQL 18 | `pg_dump`, `pg_restore` cho backup và bộ test |
| Codex CLI đã đăng nhập | Mặc định dùng cho coding agent; chạy `codex login status` để kiểm tra |
| API key và model có quyền truy cập | Chỉ cần nếu chọn `QH_MODEL_PROVIDER=openai` |
| Các repository Git và một thư mục workspace | Dữ liệu của Project |

Không cần Node trên host cho demo: Node có trong sandbox. Không cần API key để
khởi tạo Project, index, search, ask hay tạo report. Coding agent dùng hạn mức
Codex của tài khoản đã đăng nhập hoặc phát sinh chi phí API nếu chọn provider API.
Nếu chưa có CLI, cài theo [hướng dẫn Codex CLI](https://learn.chatgpt.com/docs/codex/cli),
sau đó chạy `codex login` trên máy chạy worker.

Kết quả hiện có được đo trên macOS Apple M1, RAM 16 GiB; đây không phải cấu hình
tối thiểu đã được xác nhận. Dành thêm dung lượng cho Docker image, database và
index. Benchmark một triệu file cần ít nhất 10 GB trống ngoài nhu cầu thông thường.
Linux có cấu hình CI, nhưng walkthrough trên host Linux mới vẫn chưa được xác nhận.

### macOS

Cài [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/)
và khởi động ứng dụng. Nếu dùng Homebrew:

```bash
brew install python@3.12 git ripgrep postgresql@18
export PATH="$(brew --prefix postgresql@18)/bin:$PATH"
```

Không cần bật PostgreSQL của Homebrew nếu dùng database Docker. Ghi cấu hình PATH
vào shell profile nếu muốn dùng sau khi mở terminal mới.

### Ubuntu 24.04

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv git ripgrep
```

Cài Docker Engine và Compose plugin theo
[hướng dẫn Docker cho Ubuntu](https://docs.docker.com/engine/install/ubuntu/).
Cài PostgreSQL client 18 theo [hướng dẫn PostgreSQL Ubuntu](https://www.postgresql.org/download/linux/ubuntu/)
(kho PGDG), rồi cài `postgresql-client-18`. Client mặc định của Ubuntu có thể
cũ hơn server 18 và không dump được database này. Bảo đảm tài khoản hiện tại
chạy được Docker theo chính sách quản trị máy của bạn.

### Kiểm tra công cụ

```bash
python3.12 --version
git --version
rg --version
docker info
docker compose version
pg_dump --version
pg_restore --version
```

Python phải là 3.12.x, hai client PostgreSQL phải là 18.x. `docker info` phải kết
nối được daemon. Cổng mặc định: database `127.0.0.1:55432`, HTTP `127.0.0.1:8765`.

## 2. Lấy source và cài package

Trên trang GitHub của project, chọn **Code**, copy URL clone thật, chạy `git clone`
với URL đó và `cd` vào thư mục vừa clone. Sau đó:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --constraint constraints.txt -e '.[dev]'
python -m pip check
qh --help
```

`.[dev]` bao gồm công cụ test/lint/type. Nếu chỉ sử dụng, có thể thay bằng `-e .`;
vẫn dùng `--constraint constraints.txt`. Các lệnh Alembic, Compose, template demo
và script vận hành trong hướng dẫn cần checkout source, không chỉ wheel.

## 3. Cấu hình môi trường

Nếu chưa có `.env`, copy `.env.example` thành `.env`. Không ghi đè file cấu hình
đã có. `.env` bị Git ignore; không commit file này hoặc API key.

```bash
cp -n .env.example .env
chmod 600 .env
set -a
source .env
set +a
export QH_DATA_DIR="$PWD/.tmp/qharness-data"
```

Q-Harness không tự đọc `.env`. `source` thực thi nội dung shell: chỉ load file do
bạn kiểm soát. Khi ghi giá trị có khoảng trắng/ký tự shell vào `.env`, dùng dấu
nháy phù hợp. Nên dùng đường dẫn tuyệt đối cho `QH_DATA_DIR` nếu chuyển thư mục.

| Biến | Cách sử dụng |
|------|--------------|
| `QH_DATABASE_URL` | URL SQLAlchemy `postgresql+psycopg://...`; mặc định khớp Compose |
| `QH_DATA_DIR` | Thư mục dữ liệu/artifact, không chứa source repository |
| `QH_PROJECT_ID` | UUID Project; chỉ thêm sau khi tạo Project, không để chuỗi rỗng |
| `QH_LOCAL_TOKEN` | Token ít nhất 32 ký tự, bắt buộc cho HTTP/MCP |
| `QH_MODEL_PROVIDER` | Mặc định `codex`, dùng phiên đăng nhập Codex CLI trên máy; đặt `openai` để gọi Responses API trực tiếp |
| `QH_MODEL`, `OPENAI_API_KEY` | Chỉ bắt buộc khi `QH_MODEL_PROVIDER=openai` |
| `QH_SANDBOX_IMAGE` | Tag hoặc image ID; mặc định `q-harness-sandbox:dev` |

`qh serve --host ... --port ...` chọn địa chỉ HTTP rõ ràng. Chỉ dùng loopback.
Thông tin tài khoản trong Compose là mặc định phát triển local; deployment khác
cần cấu hình database và quyền truy cập riêng.

## 4. Bật database và build sandbox

**Cài mới:** chạy các lệnh sau. **Đã dùng Compose cũ:** đọc
[migration storage PostgreSQL 18](backup-restore.md#postgresql-18-storage) và kiểm
chứng backup/restore trước khi recreate container. Không dùng `down -v` để nâng cấp.

```bash
docker compose up -d --wait postgres
docker compose ps
docker build -f Dockerfile.sandbox -t q-harness-sandbox:dev .
alembic upgrade head
alembic current
```

Kỳ vọng PostgreSQL `healthy`, build thành công và Alembic ở revision `head`.
Sandbox cần cho coding tests và render report; có thể hoãn build nếu chỉ index/search.
Sau khi kiểm chứng image, có thể cố định bản đang chạy bằng immutable image ID:

```bash
export QH_SANDBOX_IMAGE="$(docker image inspect q-harness-sandbox:dev --format '{{.Id}}')"
```

## 5. Dùng thử và kiểm tra

Tiếp tục [hướng dẫn sử dụng](usage.md) để tạo hai repository demo, index, tìm kiếm,
chạy coding task và xuất báo cáo. Có thể thử search/report trước khi cấu hình API.

Kiểm tra nhanh môi trường phát triển:

```bash
ruff format --check .
ruff check .
mypy
python -m pip check
pytest -q --ignore=tests/performance
```

Mọi phiên pytest đều cần PostgreSQL, kể cả `tests/unit`. Role test phải có quyền
`CREATEDB`; role trong Compose đáp ứng điều này. Test tự tạo/xóa database riêng.
Không dùng tài khoản production cho test. Chi tiết benchmark và kết quả kỳ vọng
ở [hướng dẫn sử dụng](usage.md) và [verification](verification.md).

## 6. Mở lại ở terminal mới

```bash
cd /absolute/path/to/q-harness-checkout
source .venv/bin/activate
set -a
source .env
set +a
export QH_DATA_DIR="$PWD/.tmp/qharness-data"
export QH_PROJECT_ID='UUID-Project-da-tao'
docker compose start postgres
qh project status --json
```

Thay UUID mẫu bằng UUID thật. Có thể lưu UUID và đường dẫn dữ liệu tuyệt đối trong
`.env` để các terminal dùng cùng cấu hình. Token HTTP phải giống nhau giữa server
và client; không tạo token khác ở mỗi terminal. Worker và server là hai tiến trình
riêng, không tự bật khi chạy `qh init`.

## 7. Dừng và cập nhật

Dừng worker/server bằng `Ctrl+C` sau khi các execution hoàn tất. Dừng database:

```bash
docker compose stop postgres
deactivate
```

Lệnh `stop` giữ lại volume. Không xóa volume, workspace, repository hoặc dữ liệu
artifact khi còn cần kết quả. Trước khi cập nhật source/dependency/schema, thực hiện
[backup](backup-restore.md), đọc [changelog](../CHANGELOG.md), rồi cài dependency,
build image và chạy migration theo phiên bản mới.

Nếu lỗi, xem [troubleshooting](troubleshooting.md). Nếu thiếu client PostgreSQL,
sai Python hoặc Docker chưa chạy, sửa môi trường trước khi chạy lại test.
