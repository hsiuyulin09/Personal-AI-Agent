# Personal AI Agent

 - 2026/10/26 Version 1.0.0

Personal AI Agent 是一個以 Python 建立的單一使用者本機 AI 助理 (主要為小型本地模型設計)。第一版提供一般 LLM 對話、可擴充 Skill System、PostgreSQL Conversation History、Session 管理、Context Window 裁切，以及直接輸出到終端的 OpenTelemetry trace。

專案使用 OpenAI Python SDK 呼叫 OpenAI-compatible Chat Completions API，因此可以連接本機模型服務、OpenAI 或 Groq。Conversation History 會保存未裁切的原始對話；送進模型的內容則由 Context Window Manager 依輪數與估算 token 上限裁切。

## 目前功能

- 一般繁體中文聊天。
- 依 Skill metadata 在一般聊天與 Skill 流程之間路由。
- Skill 內的 references、受白名單限制的 scripts、Context Builder 與共用 Responder。
- PostgreSQL 保存 Sessions 與完整 user／assistant messages。
- 每輪 user 與 assistant 使用相同 `turn_id`。
- 只載入完整回合；流程失敗留下的單獨 user message 不會進入下一輪 Context。
- Session 建立、列出、切換、改名、刪除及歷史顯示。
- Session 可使用完整 UUID、至少 8 碼 UUID 前綴或完整 title 指定。
- 依 `max_turns` 與粗略 token 估算建立 Context Window，不改寫 Database 原文。
- 終端 trace 顯示節點、時間、狀態、模型、錯誤與 token 用量。
- Docker Compose PostgreSQL、Alembic migration 與獨立測試 Database。

## 第一版限制

- RAG、Query Rewrite、向量檢索與文件 ingestion 尚未實作。
- 長期語意記憶與 Weaviate 尚未實作。
- `InMemorySaver` 只保存目前 process 的 LangGraph 流程快照，原始對話以 PostgreSQL 為準。
- Context token 數是本機粗略估算，不是模型 tokenizer 的精確結果。
- 目前是同步單人 CLI，沒有 Web UI、REST API、登入或多使用者隔離。
- 沒有自動重試、持久化 trace 或完整 Database application logging。
- 私有 Skills 預設受 `.gitignore` 的 `skills/` 規則排除；clone 後沒有 Skill 仍可正常一般聊天。

## 簡述系統流程

```text
User Input
├─ q / quit
│  └─ 結束程式
├─ /session ...
│  └─ CLI Command Router → SessionManager → Conversation Store
│     不呼叫 LLM，也不寫入 messages
└─ 一般輸入
   └─ 保存原始 User Message
      → 載入同一 Session 的先前完整回合
      → Context Window Manager
      → System Hint
         ├─ llm_chat → General Chat
         ├─ skill → Skill Hinter → Resource Router
         │          → references / allowlist scripts
         │          → Context Builder → Responder
         └─ rag → 預留路徑，目前未實作
      → 保存原始 Assistant Message
```

沒有登錄任何 Skill 且沒有 RAG metadata 時，系統會直接走 `llm_chat`，不會因 Skill 目錄不存在而停止運作。

## 目錄

- [目前功能](#目前功能)
- [第一版限制](#第一版限制)
- [簡述系統流程](#簡述系統流程)
- [檔案結構](#檔案結構)
- [開發環境及需求](#開發環境及需求)
- [快速開始](#快速開始)
- [Session 指令](#session-指令)
- [第一版手動驗收](#第一版手動驗收)
- [Conversation History 與 Context Window](#conversation-history-與-context-window)
- [Skill System](#skill-system)
- [LLM 與系統設定](#llm-與系統設定)
- [Trace 與除錯](#trace-與除錯)
- [Database 測試](#database-測試)
- [Docker 與資料生命週期](#docker-與資料生命週期)
- [常見問題](#常見問題)
- [安全與隱私](#安全與隱私)
- [開發筆記](#開發筆記)
- [License](#license)
- [關於作者](#關於作者)

## 檔案結構

```text
Personal-AI-Agent/
├─ main.py                         # CLI 入口與資源生命週期
├─ cli_command_router.py           # Session 指令解析與終端輸出
├─ session_manager.py              # Session use cases 與目前 Session
├─ system_orchestrator.py          # Context、路由與回覆流程
├─ context_window_manager.py       # 輪數／token 裁切
├─ llm_client.py                   # OpenAI-compatible client
├─ llm_chat.py                     # 一般聊天路徑
├─ trace_utils.py                  # 終端 trace 與 token 統計
├─ configs/
│  ├─ llm_config.yaml              # Provider、model、生成參數
│  ├─ system_config.yaml           # Context Window、Connection Pool
│  └─ skill_config.yaml            # Script allowlist、timeout、完整表格回覆
├─ database/
│  ├─ connection.py               # 共用 PostgreSQL Connection Pool
│  ├─ conversation_history/
│  │  ├─ store.py                  # 資料模型與 Store Protocol
│  │  ├─ postgres_store.py         # PostgreSQL Store 實作
│  │  └─ test_postgres_store.py    # PostgreSQL integration tests
│  ├─ docker_init/                 # 建立測試 Database
│  └─ migrations/                  # Alembic migrations
└─ skill_system/                   # 泛用 Skill 載入、路由與 script 執行框架
   ├─ __init__.py                  # Python package 標記
   ├─ load_skills.py               # 掃描 SKILL.md、載入 metadata 與 references
   ├─ skill_state.py               # Skill metadata、IDs 與完整表格選項狀態
   ├─ skill_orchestrator.py        # Skill Hinter、Resource Router、Context Builder
   ├─ skill_prompts.py             # Skill 各 LLM node 的共用 prompts
   ├─ skill_schemas.py             # Skill 結構化輸出的 Pydantic schemas
   ├─ skill_config.py              # 讀取 configs/skill_config.yaml
   ├─ skill_tools.py               # Script allowlist、參數正規化與 subprocess 執行
   ├─ full_table_responses.py      # 完整表格偵測與替代回覆
   └─ skills/                      # 本機 Skills，預設由 .gitignore 排除
      # (user 要使用自製 skill 時須自行新增名為 "skills" 的目錄並將 skill 放入目錄即可)
```

## 開發環境及需求

- Python 3.11
- Conda、Miniforge 或其他 Python virtual environment 工具
- Docker Desktop 與 Docker Compose
- 一個可用的 OpenAI-compatible Chat Completions provider
- Windows PowerShell 或其他 shell 可使用等價指令

結構化路由節點會要求模型輸出 JSON object。自訂本機模型服務除了相容 `/v1/chat/completions`，也必須能可靠遵循 JSON 輸出要求。

## 快速開始

以下指令請在 Repository 根目錄執行。

### 1. 下載 Repository

```powershell
git clone https://github.com/hsiuyulin09/Personal-AI-Agent.git
Set-Location Personal-AI-Agent
```

若已經取得專案，直接進入 Repository 根目錄即可。

### 2. 建立 Python 環境

```powershell
conda create -n person-ai-agent python=3.11 -y
conda activate person-ai-agent
python -m pip install -r requirements.txt
```

不使用 Conda 時，也可以使用 Python 3.11 的 `venv`。

確認當前直譯器：

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

### 3. 建立 `.env`

```powershell
Copy-Item .env.example .env
```

開啟 `.env`，至少將三處 `YOUR_LOCAL_PASSWORD` 改成同一組本機 PostgreSQL 密碼：

```dotenv
POSTGRES_DB=personal_ai_agent
POSTGRES_USER=personal_ai_agent
POSTGRES_PASSWORD=replace_with_your_password
POSTGRES_PORT=5432

POSTGRES_DSN=postgresql://personal_ai_agent:replace_with_your_password@localhost:5432/personal_ai_agent
POSTGRES_TEST_DSN=postgresql://personal_ai_agent:replace_with_your_password@localhost:5432/personal_ai_agent_test
```

`.env` 已被 Git 忽略。不要提交 API key、Database password 或完整私人 DSN。

### 4. 選擇 LLM Provider

設定檔位於 `configs/llm_config.yaml`。

#### 本機 OpenAI-compatible Server

Repository 預設：

```yaml
provider: local_qwen
```

預設 endpoint 與 model：

```yaml
base_url: "http://127.0.0.1:8080/v1/"
api_key: local
model: "qwen3-vl-8b"
```

請先使用自己的 llama.cpp、vLLM 或其他 OpenAI-compatible runtime 啟動模型服務。模型服務不包含在本 Repository，也不會由 `python main.py` 自動啟動。

若 server 支援 models endpoint，可先確認：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/v1/models
```

#### OpenAI

將 `configs/llm_config.yaml` 改成：

```yaml
provider: openai
```

並在 `.env` 設定：

```dotenv
OPENAI_API_KEY=your_api_key
```

#### Groq

將 provider 改成：

```yaml
provider: groq
```

並依目前設定使用小寫環境變數名稱：

```dotenv
groq_api_key=your_api_key
```

雲端 provider 可能產生費用；請自行確認帳號額度、model availability 與資料政策。

### 5. 啟動 PostgreSQL

請先確認 Docker Desktop 已啟動，再執行：

```powershell
docker compose config
docker compose up -d
docker compose ps
```

`docker compose config` 會解析 `.env` 並驗證 Compose 設定；請注意它的輸出可能包含展開後的 Database password，不要直接貼到公開 issue 或 log。啟動成功時 PostgreSQL service 應顯示 `healthy`。第一次建立 Docker volume 時，`database/docker_init/create_test_database.sql` 也會建立 `personal_ai_agent_test`。

`docker compose up -d` 會啟動 container，但不會啟動 Docker Desktop／Docker Engine 本身。

### 6. 套用正式 Database Migration

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic heads
```

目前成功結果應包含：

```text
0001 (head)
```

需要查看完整 Migration 順序時執行：

```powershell
python -m alembic history
```

Migration 會在 `personal_ai_agent` 建立：

```text
Database: personal_ai_agent
└─ Schema: conversation_history
   ├─ Table: conversations
   └─ Table: messages
```

### 7. 啟動 Agent

確認 PostgreSQL 與所選 LLM provider 都可用後執行：

```powershell
python main.py
```

啟動時會顯示目前 provider、model 與已登錄 Skill IDs。第一次啟動且 Database 沒有 Session 時，系統會自動建立一個未命名 Session。

輸入一般文字即可聊天；輸入以下任一指令結束：

```text
q
quit
```

程式結束時會在 `finally` 關閉 PostgreSQL Connection Pool。本機模型 server 與 Docker PostgreSQL 是獨立 process，需要分別停止。

## Session 指令

輸入：

```text
/session
/session help
```

兩者都會顯示目前支援的指令。

### 查看目前 Session

```text
/session current
```

### 列出 Sessions

```text
/session list
/session list --full
```

預設顯示 UUID 前 8 碼；`--full` 顯示完整 UUID。行首 `*` 代表目前 Session。

### 建立 Session

```text
/session new
/session new "研究筆記"
```

title 可省略。建立成功後會立即切換到新 Session。

### 切換 Session

```text
/session use 12345678
/session use 12345678 10
/session use "研究筆記" all
```

第一個參數可使用完整 UUID、至少 8 碼 UUID 前綴或完整 title。第二個參數控制切換後顯示的歷史回合數：

- 未輸入：最近 5 輪
- 正整數：最近指定輪數
- `all`：全部完整回合

這個顯示數量不會改變送進 LLM 的 Context Window 上限。

### 重新命名 Session

```text
/session rename 12345678 "新的名稱"
/session rename "舊名稱" "新的名稱"
```

title 可以重複。如果 title 或短 ID 命中多筆，系統會拒絕操作並要求使用更長的 UUID 前綴。

### 顯示歷史

```text
/session history
/session history 10
/session history all
/session history 12345678 5
/session history "研究筆記" all
```

History 只顯示同時具有 user 與 assistant 的完整回合。它不會顯示流程失敗後留下的單獨 user message。

### 刪除 Session

```text
/session delete 12345678 --confirm
```

刪除會移除 `conversations` row，並透過 PostgreSQL `ON DELETE CASCADE` 永久刪除該 Session 的所有 messages。刪除目前 Session 時，系統會切換到其他最近 Session；若已無 Session，會建立新的未命名 Session。

目前沒有「保留 Session 但清空 messages」指令。

## 第一版手動驗收

以下流程會在正式 `personal_ai_agent` Database 建立一次性 Sessions 與對話。開始前請確認 PostgreSQL healthy、正式 migration 位於 head，且所選 LLM provider 已可使用。測試 title 若已存在，請自行加上日期或其他唯一後綴，避免 title 歧義。

### 1. 一般聊天與歷史寫入

啟動 Agent：

```powershell
python main.py
```

依序輸入：

```text
/session list --full
/session new "readme-smoke-main-01"
/session current
這是 README 一般聊天 smoke test，請簡短回覆已收到。
/session history all
```

確認：

- 新 Session 成為目前 Session，行首會顯示 `*`。
- 一般聊天產生 Assistant Response。
- Trace 至少包含 `llm_chat` 與 `system`；有登錄 Skill 時，前面還會出現 `system_hint`。
- `/session history all` 顯示剛才的 user／assistant 完整回合。
- History 不包含 `/session new`、`/session current` 或其他管理指令。

### 2. 重新命名與 Session 隔離

繼續在同一個 Agent process 輸入：

```text
/session rename "readme-smoke-main-01" "readme-smoke-main-renamed-01"
/session new "readme-smoke-isolation-01"
/session history all
這是第二個 Session 的隔離測試，請簡短回覆已收到。
/session history all
/session use "readme-smoke-main-renamed-01" all
```

確認：

- 新建立的 `readme-smoke-isolation-01` 在尚未聊天前顯示沒有完整對話紀錄。
- 第二個 Session 聊天後，只顯示自己的測試回合。
- 切回 `readme-smoke-main-renamed-01` 後，只顯示第一個 Session 的內容。
- 兩個 Session 的 messages 沒有互相混用。

### 3. 程式重啟延續

切回第一個 Session 後，再輸入一則一般訊息，讓它成為最近更新的 Session：

```text
這是程式重啟前的持久化測試，請簡短回覆已收到。
quit
```

重新啟動：

```powershell
python main.py
```

接著輸入：

```text
/session current
/session history all
```

目前 Session 應為 `readme-smoke-main-renamed-01`，並能讀回重啟前的完整回合。這代表原始歷史來自 PostgreSQL，而不是只存在於前一個 Python process。

### 4. 清理手動測試資料

確認不再需要測試資料後輸入：

```text
/session delete "readme-smoke-isolation-01" --confirm
/session delete "readme-smoke-main-renamed-01" --confirm
/session list --full
quit
```

刪除會透過 `ON DELETE CASCADE` 永久移除兩個測試 Session 的 messages。若測試中途使用了不同 title，請改用 `/session list --full` 顯示的完整 UUID 刪除。

### 5. 有安裝本機 Skill 時的路由驗收

重新執行：

```powershell
python main.py
```

啟動畫面的 `Skill list` 應包含預期的 Skill ID。輸入一個明確符合該 Skill metadata 的查詢後，依 Skill 是否需要 script，trace 應依序出現下列節點：

```text
system_hint
hint
resource_router
context_builder
responder
system
```

若 `Skill list: []`，跳過此項；公開 Repository 預設不包含受 `.gitignore` 排除的本機 Skills。

## Conversation History 與 Context Window

PostgreSQL 保存完整、未裁切的原始 user／assistant 訊息。每次一般對話的順序為：

1. 產生新的 `turn_id`。
2. 先保存原始 User Message。
3. 載入相同 Session 的先前完整回合。
4. Context Window Manager 依設定裁切。
5. 執行一般聊天或 Skill 流程。
6. 回答成功後，以相同 `turn_id` 保存 Assistant Message。

若模型、script 或驗證在中途失敗，User Message 可能已保存，但沒有對應 Assistant Message。這筆不完整回合保留供追蹤，不會被 `load_recent_turns()` 載入下一輪 Context。

Context Window 設定位於 `configs/system_config.yaml`：

```yaml
context_window_manager:
  max_turns: 5
  max_context_tokens: 8000
  checkpointer: memory
```

- `max_turns`：最多載入幾個先前完整回合。
- `max_context_tokens`：粗略估算的 Context 上限。
- `checkpointer: memory`：使用 LangGraph `InMemorySaver` 保存流程快照。

裁切只影響本輪送給模型的 Context，不會刪除或改寫 PostgreSQL 原文。

## Skill System

Skill framework 會從以下位置尋找 Skill：

```text
skill_system/skills/<skill-id>/SKILL.md
```

`.gitignore` 預設排除所有 `skills/` 目錄，因此個人 Skill、references、JSON 資料與 scripts 不會自動提交到 Git。這能降低私人資料意外公開的風險，但也代表公開 clone 預設沒有內建 Skill。

最小結構：

```text
skill_system/skills/example-skill/
├─ SKILL.md
├─ references/
│  └─ example_index.md
└─ scripts/
   └─ query.py
```

`SKILL.md` 必須以 YAML front matter 開始，並提供路由與資源資訊：

```markdown
---
name: example-skill
description: Describe exactly when this skill should be selected.
capabilities:
  - example_lookup
references:
  example_index:
    path: ./references/example_index.md
    description: Select the required references and scripts.
scripts:
  example_query:
    path: ./scripts/query.py
    description: Query validated local data.
---

# Example Skill

Skill-specific instructions belong here.
```

目前 Skill Orchestrator 需要至少一個 reference key 以 `_index` 結尾，並使用該檔案指導 Resource Router 選擇本輪 references 與 scripts。

若 Skill 註冊 script，還必須在 `configs/skill_config.yaml` 登錄固定參數順序：

```yaml
script_argument_order:
  example_query:
    - operation
    - query
```

Script 執行安全邊界：

- `script_id` 必須同時存在於 `SKILL.md` 與 `skill_config.yaml`。
- 參數 key 只能使用 allowlist。
- Script path 必須位於自己的 Skill 目錄內。
- Script 以目前 Python interpreter 的 subprocess 執行。
- stdout 必須是單一可解析 JSON；診斷訊息不要混入 stdout。
- 執行時間受 `script_timeout_seconds` 限制。
- references 也不能跳出 Skill 根目錄。

完整 JSON table 若使用 `references/*table.json`，其 `metadata` 需包含 `reference_key`、`name` 與 `description`。可在 `configs/skill_config.yaml` 的 `full_table_direct_responses` 設定避免把完整表格送進模型的直接回覆。

若確定某個 Skill 適合公開，請先檢查其中沒有私人資料、公司文件、secrets 或不適合散布的內容，再調整 `.gitignore`。不要在不理解內容時直接強制加入整個 `skills/`。

## LLM 與系統設定

### `configs/llm_config.yaml`

- `provider`：目前使用的 provider key。
- `base_url`：OpenAI-compatible API root。
- `api_key`／`api_key_env`：固定開發值或 `.env` 變數名稱。
- `model`：傳給 Chat Completions API 的 model ID。
- `timeout`：SDK request timeout，單位由 OpenAI SDK 接受的格式決定。
- `generation.temperature`：一般回答 temperature。
- `generation.max_tokens`：單次回答最大輸出 token。
- `generation.presence_penalty`：presence penalty。

System Hint、Skill Hinter、Resource Router 與 Context Builder 會使用 temperature `0` 的 agent parameters，以提高結構化路由穩定性。

### `configs/system_config.yaml`

- `context_window_manager.max_turns`
- `context_window_manager.max_context_tokens`
- `context_window_manager.checkpointer`
- `postgresql.pool_min_size`
- `postgresql.pool_max_size`

Connection Pool 上限是同一個 pool 同時可借出的 PostgreSQL connections 數量，不是 Database 數量上限。

### `configs/skill_config.yaml`

- `script_argument_order`：script allowlist 與 CLI 位置參數順序。
- `full_table_direct_responses`：特定完整表格查詢的直接回答。
- `full_table_substitute_response`：未設定個別回答時的替代文字。
- `script_timeout_seconds`：Skill subprocess timeout。

## Trace 與除錯

每個 LLM 節點會在終端輸出：

```text
Node_name
duration
status
provider
model
error_type
error_message
llm_token
Evaluate
```

`TokenTracker` 會顯示：

- `batch_token`：目前這一輪所有 LLM 節點的 token 總和。
- `total_token`：程式啟動後累積 token。

結構化節點會使用 Pydantic strict models 驗證 JSON。若模型回傳錯誤型別、漏欄位或額外欄位，流程會保留 ValidationError，而不是繼續使用無效結果。

Trace 可能包含 route reason、selected context、script arguments 或其他對話衍生資料。分享終端紀錄前請先檢查私人內容。

## Database 測試

測試會清空測試 Database 的 `conversation_history.messages` 與 `conversation_history.conversations`。Fixture 會拒絕任何 database name 不以 `_test` 結尾的 `POSTGRES_TEST_DSN`，但執行前仍應自行確認 DSN。

### 1. 確認測試 Database 存在

新的 Docker volume 會透過 `database/docker_init/create_test_database.sql` 建立：

```text
personal_ai_agent_test
```

初始化 SQL 只在 PostgreSQL data directory 第一次建立時執行。若沿用較舊 volume，請先確認測試 Database 是否存在。

先從 `.env` 取得 PostgreSQL 使用者與測試 Database 名稱，再執行唯讀查詢：

```powershell
$postgresUser = python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['POSTGRES_USER'])"
$testDatabase = python -c "from dotenv import dotenv_values; from psycopg.conninfo import conninfo_to_dict; print(conninfo_to_dict(dotenv_values('.env')['POSTGRES_TEST_DSN'])['dbname'])"
docker compose exec postgres psql -U $postgresUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$testDatabase';"
```

存在時會輸出：

```text
1
```

若沒有任何輸出，建立測試 Database：

```powershell
docker compose exec postgres createdb -U $postgresUser $testDatabase
```

`createdb` 只需執行一次；Database 已存在時不要重複建立。

### 2. 對測試 Database 套用 Migration

目前 Alembic 只讀取 `POSTGRES_DSN`，因此在 PowerShell 暫時將它指向 `.env` 的 `POSTGRES_TEST_DSN`：

```powershell
$env:POSTGRES_DSN = python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['POSTGRES_TEST_DSN'])"
python -m alembic upgrade head
python -m alembic current
Remove-Item Env:POSTGRES_DSN
```

成功結果應為：

```text
0001 (head)
```

`Remove-Item` 只清除目前 PowerShell process 的暫時覆蓋值；`.env` 不會被刪除或修改。

### 3. 檢查 Git 追蹤的 Python 程式

```powershell
$pythonFiles = git ls-files "*.py"
python -m py_compile $pythonFiles
```

這會對公開版本中由 Git 追蹤的 Python 檔案進行語法編譯檢查，刻意不包含被 `.gitignore` 排除的私人 Skills。成功時不會輸出內容，且 process exit code 為 `0`。

### 4. 檢查 Context Window 裁切

```powershell
python -c "from context_window_manager import ContextWindowManager; from langgraph.checkpoint.memory import InMemorySaver; history = [{'role': role, 'content': f'{role}{turn}'} for turn in range(1, 8) for role in ('user', 'assistant')]; manager = ContextWindowManager(2, 1000, InMemorySaver()); print([message['content'] for message in manager.prepare_context('current', history, 'readme-context-test')])"
```

這個獨立檢查建立 7 輪模擬歷史，並把 `max_turns` 設為 `2`。成功時只保留最新兩輪：

```text
['user6', 'assistant6', 'user7', 'assistant7']
```

此指令不連接 PostgreSQL，也不會寫入正式或測試 Database。

### 5. 執行 Database Integration Tests

```powershell
python -m pytest database/conversation_history/test_postgres_store.py -v
```

目前公開 Repository 的完整測試套件也可以直接執行：

```powershell
python -m pytest -v
```

目前測試檔包含 5 個案例，驗證：

- Conversation 建立、取得與不存在結果。
- 完整 turn、role、content 與 JSONB metadata round trip。
- 只載入先前完整回合，排除不完整回合與目前回合。
- 重複 role 觸發 UNIQUE constraint 後，transaction rollback 且 pool 仍可使用。
- 不同 Session 的 messages 互相隔離。

成功摘要應類似：

```text
5 passed
```

執行秒數會因電腦而異，不應作為成功條件。

## Docker 與資料生命週期

從 `.env` 取得正式 Database 連線所需名稱：

```powershell
$postgresUser = python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['POSTGRES_USER'])"
$postgresDatabase = python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['POSTGRES_DB'])"
```

檢查 PostgreSQL 是否接受連線：

```powershell
docker compose exec postgres pg_isready -U $postgresUser -d $postgresDatabase
```

成功結果應包含 `accepting connections`。

查看最近 100 行 PostgreSQL logs：

```powershell
docker compose logs --tail 100 postgres
```

持續追蹤 logs：

```powershell
docker compose logs -f postgres
```

使用 `Ctrl+C` 停止追蹤只會離開 log 畫面，不會停止 PostgreSQL container。

以下是正式 Database 的唯讀檢查指令，不會修改對話資料：

```powershell
docker compose exec postgres psql -U $postgresUser -d $postgresDatabase -c '\dt conversation_history.*'
docker compose exec postgres psql -U $postgresUser -d $postgresDatabase -c 'SELECT session_id, title, updated_at FROM conversation_history.conversations ORDER BY updated_at DESC;'
docker compose exec postgres psql -U $postgresUser -d $postgresDatabase -c 'SELECT session_id, COUNT(*) AS message_count FROM conversation_history.messages GROUP BY session_id ORDER BY session_id;'
```

停止 PostgreSQL，但保留 container 與資料：

```powershell
docker compose stop
```

移除 container 與 network，但保留 named volume：

```powershell
docker compose down
```

重新啟動：

```powershell
docker compose up -d
```

以下指令會永久刪除 Docker volume、正式 Conversation History 與測試資料：

```powershell
docker compose down -v
```

除非確定不需要既有對話，否則不要使用 `-v`。

## 常見問題

### `ModuleNotFoundError: No module named 'langgraph'`

通常表示使用了錯誤的 Python environment，或尚未安裝 requirements：

```powershell
conda activate person-ai-agent
python -m pip install -r requirements.txt
```

### Docker 指令無法連線

`docker compose up -d` 不能啟動 Docker Desktop 本身。請先啟動 Docker Desktop，等待 Docker Engine ready，再執行 Compose 指令。

### PostgreSQL connection refused

確認：

```powershell
docker compose ps
```

接著檢查 `.env` 的 password、port、`POSTGRES_DSN` 與 container 設定是否一致。如果 host 的 `5432` 已被占用，可以修改 `POSTGRES_PORT`，並同步修改兩個 DSN 的 port。

### `relation conversation_history... does not exist`

目標 Database 尚未套用 migration。正式 Database 與測試 Database 必須分別執行 `alembic upgrade head`。

### 找不到 `personal_ai_agent_test`

初始化 SQL 只在建立全新 volume 時執行。可以建立新的開發 volume，或在確認目標 PostgreSQL 後手動建立測試 Database。不要為了建立測試 Database 而誤刪仍需要的正式 volume。

### 找不到 API key

確認 `configs/llm_config.yaml` 的 `provider`，以及對應的 `.env` key：

- OpenAI：`OPENAI_API_KEY`
- Groq：`groq_api_key`
- 預設 local_qwen：設定檔內使用本機開發值 `local`

### 本機模型無法連線

確認本機 OpenAI-compatible server 正在監聽設定的 `base_url`。`python main.py` 不會啟動或停止模型 server；通常需在模型 server 所在終端使用 `Ctrl+C` 停止。

### Pydantic ValidationError

查看 trace 中發生錯誤的 `Node_name` 與原始 ValidationError。這通常表示模型沒有遵守結構化 JSON schema。確認模型具有足夠的 instruction-following 能力，且 Skill metadata、script arguments 與 prompt schema 一致。

### 啟動時顯示 `Skill list: []`

這是沒有安裝本機 Skill 時的正常狀態。系統會直接使用一般聊天。若預期應有 Skill，確認目錄為 `skill_system/skills/<skill-id>/SKILL.md`。

## 安全與隱私

- `.env` 不得提交到 Git。
- PostgreSQL 會保存完整原始對話；請依資料敏感度保護 Docker volume 與備份。
- 個人 Skills 可能包含私人 JSON、公司文件或可執行 scripts，預設不進 Git。
- Skill scripts 是本機程式碼；只安裝及執行可信來源。
- 不要將 PostgreSQL port、本機模型 API 或未加驗證的 Agent 直接暴露到公網。
- 雲端 LLM provider 會收到送入該 provider 的 Context；使用前請確認隱私與資料保留政策。
- `/session delete ... --confirm` 會永久刪除該 Session 的 Database 紀錄。

## 開發筆記

第一版核心程式已完成主要接線，目前重點是正式 PostgreSQL Session CLI、Context 裁切、程式重啟延續、Session 隔離與 trace 的整合驗證。RAG、長期語意記憶、多 Skill 同輪執行與 Web UI 或將於後續版本更新。

## 關於作者

林修渝 LIN, Hsiu-Yu

臺灣人，來自台南市。喜歡戰錘40k、喜歡音樂、喜歡騎車、喜歡一切亂七八糟對工作沒什麼幫助的事情。

我是一名生物化學碩士，曾任職中央研究院生醫所研究助理，現職 AI 生物資訊工程師。專長是生物化學、癌症細胞生物學、外泌體、生物醫學數據分析、LLM 應用部屬、RAG、Agent Skill。

Lin, Hsiu-Yu

A AI bioinformatic engineer hailing from Taiwan. I’m passionate about Warhammer 40k, music, motorcycle touring, and baseball. Basically, anything and everything that has absolutely nothing to do with my job.

I am a Master of Biochemistry and a former Research Assistant at the Institute of Biomedical Science, Academia Sinica. Now, I work as an AI Bioinformatics Engineer, and specialize in biochemistry, cancer cell biology, exosomes, biomedical data analysis, LLM application deployment, RAG, and Agent Skills.

GitHub : https://github.com/hsiuyulin09
