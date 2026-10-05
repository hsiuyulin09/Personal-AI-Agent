# PostgreSQL database 測試檔
# 與正式版依賴相同的 container 和 migration 等環境, 格式與規格都相同, 僅 db 不同
from collections.abc import Iterator
from os import getenv
from pathlib import Path
from uuid import UUID, uuid4
from dotenv import load_dotenv
import pytest # 提供 fixture、測試失敗與例外驗證等功能

from psycopg.conninfo import conninfo_to_dict
    # conninfo_to_dict 會將 PostgreSQL DSN 拆成可讀取欄位的 dict (value: user, password, host, port, dbname)
from psycopg.errors import UniqueViolation
from psycopg_pool import ConnectionPool

from database.connection import create_connection_pool, close_connection_pool
from database.conversation_history.postgres_store import PostgresConversationHistoryStore


PROJECT_ROOT = Path(__file__).resolve().parent[2]


# 測試完成後刪除測試資料
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

# 建立測試連線池
@pytest.fixture(scope="session")
def pool():
    load_dotenv(PROJECT_ROOT/".env")
    test_dsn = getenv("POSTGRES_TEST_DSN")

    # dsn 不存在時立即失效
    if not test_dsn:
        pytest.fail("POSTGRES_TEST_DSN must be set in .env")

    database_name = str(conninfo_to_dict(test_dsn).get("dbname"))

    # 用資料庫命名確認開發者已指定為測試資料庫
    if not database_name.endswith("_test"): # endswith 字串方法, 檢查並比對指定字串結尾
        pytest.fail("POSTGRES_TEST_DSN must point to a database ending with '_test'")

    connection_pool = create_connection_pool(dsn=test_dsn, min_size=1, max_size=2)

    yield connection_pool
    close_connection_pool(connection_pool)
