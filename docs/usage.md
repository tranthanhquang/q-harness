# Sử dụng và test Q-Harness

Hướng dẫn demo từ source checkout; cần hoàn thành [cài đặt](installation.md).
Chạy trong terminal đã activate `.venv`, load cấu hình và đứng ở gốc checkout.
Q-Harness hiện dùng CLI/HTTP/MCP, chưa có giao diện web.

## 1. Kiểm tra trước khi chạy

```bash
qh --help
docker compose ps
alembic current
python -m pip check
```

PostgreSQL phải healthy và schema ở `head`. Không cần API key cho các bước
Project/index/search/ask/report. Build sandbox trước khi tạo report hoặc chạy code.

## 2. Tạo Project demo với hai repository

Fixture builder có sẵn tạo repository Python `api`, repository TypeScript `web`,
test thực tế và file approval scope. Dữ liệu demo nằm ngoài checkout:

```bash
export QH_DEMO_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/qh-demo.XXXXXX")"
python - <<'PY'
import os
from pathlib import Path
from tests.fixtures.build import build
build(Path(os.environ["QH_DEMO_ROOT"]).resolve())
PY

export QH_PROJECT_ID="$(qh init \
  --name 'Q-Harness Demo' \
  --workspace "$QH_DEMO_ROOT/workspaces/demo" \
  --json | python -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"

qh project add "$QH_DEMO_ROOT/repositories/api" --role api --name api --json
qh project add "$QH_DEMO_ROOT/repositories/web" --role web --name web --json
qh project list --json
qh project status --json
```

Kỳ vọng: một Project UUID, hai repository có UUID/HEAD riêng. Lưu giá trị
`QH_PROJECT_ID` và `QH_DEMO_ROOT` nếu muốn dùng lại; không chạy lại builder trên
cùng thư mục sau khi đã sửa demo. `/tmp` có thể bị hệ điều hành dọn, nên dùng thư
mục bền vững nếu muốn giữ demo lâu dài.

### Dùng repository thật

Thay bước tạo fixture bằng các thư mục Git đang có. Đặt các repo ngay dưới
workspace rồi chạy `qh init` không có `--json`; harness sẽ liệt kê repo để chọn.
Nhập số để bật/tắt repo, nhấn Enter để xác nhận. Tên thư mục `fe` và `be` có role
mặc định lần lượt là `frontend` và `backend`; tên khác dùng chính tên thư mục làm
role. Nếu không tìm thấy repo, thêm bằng `qh project add` như ví dụ dưới đây.

`--json` không mở màn hình chọn và không tự add repo; sau đó dùng `qh project add`
thủ công.

```bash
qh init --name 'My Project' --workspace /absolute/path/to/workspace
export QH_PROJECT_ID='UUID-tu-ket-qua-init'
```

Chỉ chạy lệnh dưới đây nếu cần tự add repo hoặc `qh init` không tìm thấy chúng:

```bash
qh project add /absolute/path/to/api --role api --name api
qh project add /absolute/path/to/web --role web --name web
```

Thay toàn bộ đường dẫn/UUID mẫu. Chọn Project qua `QH_PROJECT_ID`, qua
`qh --project UUID COMMAND`, hoặc chạy trong workspace có `.qharness/project.yaml`.
Một canonical repository path không được đăng ký đồng thời cho nhiều Project.

## 3. Index, tìm kiếm và ask

```bash
qh project index --full --json
qh knowledge search 'health check' --json
qh ask 'health check' --json
```

Kỳ vọng kết quả chứa source của demo, repository/path và thông tin citation.
`qh ask` hiện trả excerpt từ index, không phải chat sinh câu trả lời bằng LLM.
Dùng từ khóa có trong source; một câu hỏi dài với nhiều từ không có trong file
có thể không có kết quả. Ask không tạo task hoặc sửa source.

Thử cập nhật một file rồi refresh:

```bash
echo '# demo refresh marker' >> "$QH_DEMO_ROOT/repositories/api/api.py"
qh project refresh --json
qh knowledge search 'marker' --json
```

Kỳ vọng tìm được dòng mới. Nếu source thay đổi sau index, xử lý trạng thái `STALE`
bằng refresh trước khi dựa vào kết quả. Không cần full reindex cho mỗi lần sửa file.

## 4. Giao task cho coding agent

Đây là bước có thể sửa repository và dùng hạn mức Codex hoặc gọi API tính phí. Dùng demo trước, đọc
approval scope và kiểm tra Git diff. Hủy task không tự hoàn tác những thay đổi đã ghi.

### Cấu hình provider

Mặc định worker dùng phiên đăng nhập Codex CLI chung của máy. Cài Codex CLI,
đăng nhập một lần trên máy chạy worker, rồi kiểm tra:

```bash
codex login status
```

Không cần `--profile`, `QH_MODEL` hay `OPENAI_API_KEY`. Worker dùng xác thực trong
`~/.codex` nhưng bỏ qua hooks/plugins/cấu hình cá nhân khi gọi model để giữ ranh giới
Q-Harness; tên model trong `~/.codex/config.toml` được dùng nếu có. Codex trả action JSON từ thư mục
tạm ở chế độ read-only; Q-Harness quyết định quyền ghi và kiểm thử.

Nếu muốn dùng OpenRouter, 9router hoặc gateway khác, chọn provider API trực tiếp.
Chọn tên model có quyền truy cập và nhập key bằng prompt ẩn:

```bash
export QH_MODEL_PROVIDER=openai
export OPENAI_API_KEY="$(python -c 'import getpass; print(getpass.getpass("OpenAI API key: "))')"
export QH_MODEL='ten-model-ban-co-quyen-truy-cap'
# Optional: API root for an OpenAI-compatible gateway; omit /responses.
export OPENAI_BASE_URL='https://openrouter.ai/api/v1'
export QH_SANDBOX_IMAGE="$(docker image inspect q-harness-sandbox:dev --format '{{.Id}}')"
```

`OPENAI_BASE_URL` defaults to `https://api.openai.com/v1`. For OpenRouter, use
`https://openrouter.ai/api/v1`; for 9router or another gateway, use the API root
provided by that service. The gateway must implement the OpenAI Responses API
(`/responses`), including tool calling used by coding tasks. A gateway that only
supports `/chat/completions` is not compatible with the current worker. Set the
gateway's model identifier in `QH_MODEL` and its API key in `OPENAI_API_KEY`.
Q-Harness passes the key to that gateway, so use a key issued for that provider.

### Tạo, approve, queue và chạy worker

```bash
qh run 'Change health_check and healthCheck from ok to ready in API and web, and update their tests.py and tests.mjs expectations' --json
```

Copy UUID ở `data.id` của kết quả, không dùng display ID:

```bash
export QH_TASK_ID='UUID-task-vua-tao'
cat "$QH_DEMO_ROOT/scopes/two-repo-task.json"
qh task approve "$QH_TASK_ID" --scope-file "$QH_DEMO_ROOT/scopes/two-repo-task.json" --json
qh task execute "$QH_TASK_ID" --idempotency-key demo-two-repo-0001 --json
qh worker --once
qh task status "$QH_TASK_ID" --json
git -C "$QH_DEMO_ROOT/repositories/api" diff
git -C "$QH_DEMO_ROOT/repositories/web" diff
```

`execute` chỉ queue; worker mới thực thi. `--once` xử lý một work item đang chờ,
không chọn task bằng UUID; khi demo nên tránh queue task khác cùng lúc. Dùng
`qh worker` để chạy liên tục trong terminal khác với cùng môi trường.

Scope demo chỉ cho phép hai repository, tool read/write/search/test, lệnh
Python/Node và không có network trong container. Hai required gate là
`python tests.py` và `node tests.mjs`. Với repository thật, viết scope riêng theo
[CLI contract](../specs/001-q-harness-platform/contracts/cli.md); không dùng scope
demo hoặc mở quyền toàn bộ filesystem.

Kỳ vọng task chỉ `COMPLETED` khi required tests thực sự pass. Live model có thể
thất bại; đọc evidence trong status để sửa môi trường hoặc scope. Không đánh dấu
`NOT_RUN` là pass. Dùng key idempotency mới cho một yêu cầu mới; retry cùng yêu cầu
giữ nguyên key. Task có UUID riêng dù tên/request giống nhau.

| Trạng thái | Ý nghĩa và hành động |
|------------|--------------------|
| `WAITING_APPROVAL` | Review rồi approve scope |
| `BLOCKED` | Kiểm tra approval, conflict, dependency hoặc interruption |
| `FAILED` | Workflow thất bại; đọc evidence |
| `COMPLETED` | Coding workflow và required gates hoàn tất |
| Execution `INTERRUPTED` | Task bị block; kiểm tra source trước khi tiếp tục |

Các lệnh theo dõi/điều khiển:

```bash
qh task list --json
qh notification list --json
qh task cancel "$QH_TASK_ID" --json
```

Chỉ chạy `cancel` nếu muốn dừng task. Sau khi giải quyết nguyên nhân bị block,
review source/scope rồi mới dùng `qh task continue UUID` theo trạng thái thực tế.

## 5. Xuất DOCX và XLSX

Đăng ký hai template do project cung cấp, sau khi build sandbox:

```bash
qh report template verify src/qharness/reports/templates/weekly-progress
qh report template register src/qharness/reports/templates/weekly-progress --platform --license MIT --json
qh report template verify src/qharness/reports/templates/test-results
qh report template register src/qharness/reports/templates/test-results --platform --license MIT --json
qh report generate weekly-progress --idempotency-key report-weekly-0001 --json
qh report generate test-results --idempotency-key report-tests-0001 --json
qh report list --json
```

Lấy UUID report từ kết quả và kiểm tra:

```bash
qh report status UUID-report --json
```

Kỳ vọng report `READY`, có artifact path để mở DOCX/XLSX. Nếu `FAILED`, đọc lý do;
không coi file tạm là kết quả thành công. Report dùng dữ liệu có thật, không tự
sáng tác test đã pass khi chưa chạy task. XLSX giữ formula của template nhưng
không xác nhận Excel đã tính lại công thức. Có thể mở file bằng Office/LibreOffice.

MIT áp dụng cho template demo của Q-Harness. Template bên ngoài phải có nguồn,
license và checksum hợp lệ; khai báo `--license` không tự tạo quyền sử dụng.

## 6. HTTP API và MCP

Trong terminal đã chọn Project, tạo token và chạy server:

```bash
export QH_LOCAL_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
qh serve --host 127.0.0.1 --port 8765
```

Server chạy foreground. Ở terminal thứ hai: activate venv, load cùng cấu hình,
Project UUID, đường dẫn data và **cùng token**. Có thể lưu token trong `.env` riêng
đã `chmod 600`; không đưa token vào tài liệu, Git hay screenshot.

```bash
curl -sS -H "Authorization: Bearer $QH_LOCAL_TOKEN" http://127.0.0.1:8765/healthz
curl -sS -H "Authorization: Bearer $QH_LOCAL_TOKEN" http://127.0.0.1:8765/v1/projects
curl -i http://127.0.0.1:8765/v1/projects
```

Hai request đầu được xác thực, request cuối phải bị từ chối. Health hiện trả
`database: ok`, `worker: unavailable`, `status: degraded` ngay cả khi idle worker
có thể đang chạy; kiểm tra task/heartbeat khi đánh giá execution.

MCP dùng endpoint `http://127.0.0.1:8765/mcp`. Xem
[cấu hình Codex MCP](codex-mcp.md) và [MCP contract](../specs/001-q-harness-platform/contracts/mcp-tools.md).
Client phải kế thừa token environment, truyền đúng Project ID. MVP không quảng bá
coding execution tool qua MCP; dùng CLI để approve/execute.

## 7. Chạy bộ test

Không cần live API key. Cần database role có `CREATEDB`, sandbox đã build và
PostgreSQL 18 clients trên PATH. Mỗi pytest session tạo database ngẫu nhiên rồi
xóa sau khi xong, kể cả khi chỉ chọn unit tests:

```bash
ruff format --check .
ruff check .
mypy
python -m pip check
pytest -q --ignore=tests/performance
```

Có thể kiểm tra từng nhóm để chẩn đoán:

```bash
pytest -q tests/unit
pytest -q tests/integration
pytest -q tests/contract
pytest -q tests/e2e
pytest -q tests/security
```

Kết quả đã ghi nhận: 110 tests pass trên macOS, không skip; xem
[verification](verification.md) để biết phạm vi và môi trường cụ thể. Không suy ra
live model hoặc Linux đã được kiểm chứng từ các kết quả này.

Benchmark lớn là tùy chọn, không cần cho lần dùng thử đầu tiên:

```bash
QH_RUN_SCALE=1 pytest -q tests/performance
```

Benchmark tạo một triệu file thực và database rows, cần ít nhất 10 GB trống và
nhiều thời gian hơn bộ test thường. Nó đo latency status/search/refresh, không đo
full initial indexing throughput. Không chạy trên database production.

## 8. Dừng và lưu dữ liệu

Dừng server/worker bằng `Ctrl+C` sau khi execution kết thúc, rồi
`docker compose stop postgres`. Không xóa volume để dừng dịch vụ.
Backup database và artifacts cùng lúc theo [backup/restore](backup-restore.md),
đồng thời backup source/workspace riêng. Xem [troubleshooting](troubleshooting.md)
nếu gặp `DEPENDENCY_UNAVAILABLE`, `STALE`, `FILE_CONFLICT` hoặc report lỗi.
