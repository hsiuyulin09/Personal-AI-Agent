# 通用的單一資料庫設定。

[alembic]
# Migration 腳本的路徑。
# 通常使用 POSIX 路徑格式（例如正斜線），
# 並以代號 %(here)s 為基準；該代號指向目前這個
# ini 檔案所在的位置。
script_location = %(here)s/database/migrations

# 產生 Migration 檔名時使用的範本；預設值為 %%(rev)s_%%(slug)s
# 若要在檔名前加上日期與時間，請取消下一行的註解
# 請參考 https://alembic.sqlalchemy.org/en/latest/tutorial.html#editing-the-ini-file
# 以查看所有可用的格式代號
# file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
# 也可以依照日期建立子目錄（需要設定 recursive_version_locations = true）
# file_template = %%(year)d/%%(month).2d/%%(day).2d_%%(hour).2d%%(minute).2d_%%(second).2d_%%(rev)s_%%(slug)s

# 要加入 sys.path 開頭的路徑。
# 預設為目前工作目錄。若有多個路徑，路徑分隔方式
# 由下方的 path_separator 設定。
prepend_sys_path = .


# 產生 Migration 檔案內容中的日期
# 以及檔名日期時使用的時區。
# 若有指定，必須安裝 tzdata；可以將
# `alembic[tz]` 加入 pip requirements。
# 字串值會傳入 ZoneInfo()
# 留空表示使用本機時間
# timezone =

# slug 欄位允許的最大字元長度
# truncate_slug_length = 40

# 設為 true 時，執行 revision 指令一定會載入 Migration 環境，
# 不受是否使用 autogenerate 影響
# revision_environment = false

# 設為 true 時，versions/ 目錄內即使沒有
# 對應的 .py 原始檔，仍允許將 .pyc 與 .pyo 檔案
# 辨識為 revision
# sourceless = false

# Revision 檔案位置；預設為
# <script_location>/versions。使用多個版本目錄時，
# 建立第一個 revision 必須透過 --version-path 指定位置。
# 此處使用的路徑分隔方式應與下方的 path_separator
# 設定相同。
# version_locations = %(here)s/bar:%(here)s/bat:%(here)s/alembic/versions

# path_separator 指定檔案路徑清單使用的分隔方式，
# 包含 alembic.ini 等 configparser 檔案中的
# version_locations 與 prepend_sys_path。
# 新產生的 alembic.ini 預設使用 os，也就是透過 os.pathsep
# 依照作業系統選擇適合的路徑分隔符號。
#
# 為了相容舊版 alembic.ini，如果檔案內沒有 path_separator，
# 這項預設值不會自動生效。若完全省略
# 此設定，會使用以下備援邏輯：
#
# 1. 解析 version_locations 時，先改用舊版的
#    version_path_separator 設定；若該設定也不存在，則依照舊版
#    行為使用空格及／或逗號分隔。
# 2. 解析 prepend_sys_path 時，依照舊版
#    行為使用空格、逗號或冒號分隔。
#
# path_separator 可使用以下值：
#
# path_separator = :
# path_separator = ;
# path_separator = space
# path_separator = newline
#
# 使用 os.pathsep；這是新專案使用的預設設定。
path_separator = os

# 設為 true 時，會在每個 version_locations 目錄內
# 遞迴搜尋原始檔案
# 此功能從 Alembic 1.10 開始提供
# recursive_version_locations = false

# 使用 script.py.mako 寫入 revision 檔案時
# 採用的輸出編碼
# output_encoding = utf-8

# 資料庫 URL。只有由使用者維護的 env.py 會讀取此設定。
# 也可以在 env.py 檔案內自行設定其他
# 取得資料庫 URL 的方式。
sqlalchemy.url = driver://user:pass@localhost/dbname


[post_write_hooks]
# post_write_hooks 用來定義產生新 revision 腳本後要執行的
# 腳本或 Python 函式。詳細設定與範例
# 請參考 Alembic 文件

# 使用 black 格式化：透過 console_scripts runner 呼叫 black 進入點
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# 使用 ruff 檢查並嘗試修正：透過 module runner 呼叫 ruff 模組
# hooks = ruff
# ruff.type = module
# ruff.module = ruff
# ruff.options = check --fix REVISION_SCRIPT_FILENAME

# 另一種方式是透過 exec runner 執行 PATH 中找到的可執行檔
# hooks = ruff
# ruff.type = exec
# ruff.executable = ruff
# ruff.options = check --fix REVISION_SCRIPT_FILENAME

# Logging 設定。此區段也只由使用者維護的
# env.py 讀取。
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
