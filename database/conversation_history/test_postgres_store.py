# PostgreSQL database 測試檔
from collections.abc import Iterator
from os import getenv
from pathlib import Path
from uuid import UUID, uuid4
from dotenv import load_dotenv

from psycopg.conninfo import conninfo_to_dict
from psycopg.errors import UniqueViolation
from psycopg_pool import ConnectionPool

from database.connection import create_connection_pool, close_connection_pool
from database.conversation_history.postgres_store import PostgresConversationHistoryStore


PROJECT_ROOT = Path(__file__).resolve().parent[2]


def clear_test_data(pool):
    with pool.connection() as connection:
        with connection.tansaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    # TRUNCATE TABLE 清空該 table 的 row (欄位名稱會保留)
                    # CASCADE 將前面的指令操作連帶套用到具有依賴關係的資料庫物件
                    """
                    TRUNCATE TABLE
                        conversation_history.messages
                        conversation_history.conversations
                    CASCADE
                    """
                )
