from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Alembic Config 物件讀取目前使用中的 .ini 設定值
config = context.config

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
