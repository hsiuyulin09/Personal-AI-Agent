from os import getenv
from pathlib import Path
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool # Psycopg 提供的 PostgreSQL Connection Pool

from system_config import load_system_config


# 載入環境變數
PROJECT_ROOT = Path(__file__).resolve().parents[1] # parents[0] 是 database/ # parents[1] 是 Personal-AI-Agent/
ENV_PATH = PROJECT_ROOT/".env"


# 建立共用的 PostgreSQL Connection Pool
def creat_connection_pool(dsn=None, min_size=None, max_size=None): # min_size 最少保留連線數, max_size 允許的最大連線數
    load_dotenv(ENV_PATH)
    postgre_dsn = dsn or getenv("POSTGRES_DSN")

    if not postgre_dsn:
        raise ValueError("POSTGRES_DSN must be set in .env")

    system_config = load_system_config()
    database_config = system_config.get("conversation_history_database", {}) # 是不是應該改參數分類命名?因為這是共用的

    resolved_min_size = (
        min_size
        if min_size is not None
        else database_config.get("pool_min_size", 1)
    )

    resolved_max_size = (
        max_size
        if max_size is not None
        else database_config.get("pool_max_size", 4)
    )

    if not isinstance(resolved_min_size, int) or resolved_min_size < 1:
        raise ValueError("min_size must be a positive int")

    if not isinstance(resolved_max_size, int) or resolved_max_size < 1:
        raise ValueError("max_size must be a positive int")

    if resolved_min_size > resolved_max_size:
        raise ValueError("min_size cannot be greater than max_size")

    pool = ConnectionPool( # 建立 ConnectionPool 物件
        conninfo=postgre_dsn,
        min_size=resolved_min_size,
        max_size=resolved_max_size,
        open=False # open=False 建立物件時先不要自動連線
    )

    pool.open(wait=True)
        # 明確開啟 Connection Pool
        # wait=True 會等待 Pool 完成初始連線
        # 如果 PostgreSQL 無法連線時在這裡直接報錯

    return pool


# 關閉 Connection Pool 並釋放其中的資料庫連線
def close_connect_pool(pool):
    pool.close()
