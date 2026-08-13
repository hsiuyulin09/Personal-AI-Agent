from logging.config import fileConfig
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url
from alembic import context

# Alembic Config 物件讀取目前使用中的 .ini 設定值
config = context.config

# 載入環境變數
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT/".env")

# 讀取 PostgreSQL 正式 Database 的連線 str (DSN)
postgres_dsn = getenv("POSTGRES_DSN") # postgres_dsn -> str
if not postgres_dsn:
    raise ValueError("POSTGRES_DSN must be set in .env")

# DSN 字串解析成 SQLAlchemy URL 物件
postgres_url = make_url(postgres_dsn)
if postgres_url.get_backend_name() != "postgresql":
    raise ValueError("POSTGRES_DSN must use postgresql")

# 指定 SQLAlchemy 使用 Psycopg 3 連接 PostgreSQL
sqlalchemy_url = postgres_url.set(drivername="postgresql+psycopg")

# 將 SQLAlchemy URL 物件轉成包含完整連線資料的字串
sqlalchemy_url_text = sqlalchemy_url.render_as_string(hide_password = False)

# 避免 URL 中的 "%" 被 Alembic Config 當成特殊格式
sqlalchemy_url_text = sqlalchemy_url_text.replace("%", "%%")

# 在本次執行期間覆蓋 alembic.ini 的原預設連線字串
config.set_main_option("sqlalchemy.url", sqlalchemy_url_text)

# 讀取設定檔中的 Python logging 設定，並完成 logger 初始化。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 若要使用 autogenerate，請在此加入 model 的 MetaData 物件。
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# env.py 若需要其他設定值，可以透過 config 取得：
# my_important_option = config.get_main_option("my_important_option")
# 其他設定依此類推。


def run_migrations_offline() -> None:
    """以離線模式執行 Migration。

    此模式只使用資料庫 URL 設定 context，不建立 Engine，
    但有需要時也可以在此使用 Engine。由於略過 Engine 建立，
    因此不需要可用的 DBAPI。

    在此呼叫 context.execute() 會將指定字串輸出至腳本。

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以線上模式執行 Migration。

    此模式需要建立 Engine，並將資料庫連線交給 context 使用。

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
