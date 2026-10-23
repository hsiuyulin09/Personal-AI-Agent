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


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# 測試完成後刪除測試資料
def clear_test_data(pool):
    with pool.connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    # TRUNCATE TABLE 清空該 table 的 row (欄位名稱會保留)
                    # CASCADE 將前面的指令操作連帶套用到具有依賴關係的資料庫物件
                    """
                    TRUNCATE TABLE
                        conversation_history.messages,
                        conversation_history.conversations
                    CASCADE
                    """
                )


# 建立測試連線池
@pytest.fixture(scope="session") # scope 是 keyword argument, 指定 fixture 的生命週期與共用範圍
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


@pytest.fixture(autouse=True)
# 測試前後清空 database
def clean_database(pool: ConnectionPool):
    clear_test_data(pool)
    yield
    clear_test_data(pool)


@pytest.fixture
# 測試用 pool 傳入 class PostgresConversationHistoryStore
def store(pool: ConnectionPool):
    test_database_store = PostgresConversationHistoryStore(pool)
    return test_database_store

def test_get_or_create_conversation(store:PostgresConversationHistoryStore):
    conversation = store.create_conversation(title="test session")
    get_conversation = store.get_conversation(conversation.session_id)

    assert isinstance(conversation.session_id, UUID)
    assert conversation.title == "test session"
    assert conversation.created_at <= conversation.updated_at
    assert get_conversation == conversation

    missing_session_id = uuid4()

    assert store.get_conversation(missing_session_id) is None

def test_save_and_load_complete_turn(store:PostgresConversationHistoryStore):

    # 產生測試資料
    conversation = store.create_conversation()
    turn_id = uuid4()
    metadata = {"route":"llm_chat", "tokens": {"input":10}}

    # 測試輸入 user query 和 assistant response
    user_message = store.save_user_message(conversation.session_id, turn_id, "test query", metadata)
    assistant_message = store.save_assistant_message(conversation.session_id, turn_id, "test response", metadata)

    # 調取儲存後的測試內容
    messages = store.load_recent_turns(conversation.session_id, current_turn_id=uuid4(), max_turns=1)

    assert user_message.role == "user"
    assert assistant_message.role == "assistant"
    assert dict(user_message.metadata) == metadata
    assert dict(assistant_message.metadata) == metadata
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.content for message in messages] == ["test query", "test response"]

def test_load_only_prior_complete_turns(store:PostgresConversationHistoryStore):
    conversation = store.create_conversation()

    first_turn_id = uuid4()
    second_turn_id = uuid4()
    third_turn_id = uuid4()
    incomplete_turn_id = uuid4()
    current_turn_id = uuid4()

    complete_turn_inputs = [
        (first_turn_id, "first query", "first response"),
        (second_turn_id, "second query", "second response"),
        (third_turn_id, "third query", "third response")
    ]

    complete_user_messages = []

    # complete_user_messages = [
    # (first_user_message, first_assistant_message),
    # (second_user_message, second_assistant_message)
    # ]

    for turn_id, user_content, assistant_content in complete_turn_inputs:
        user_message = store.save_user_message(conversation.session_id, turn_id, user_content)
        assistant_message = store.save_assistant_message(conversation.session_id, turn_id, assistant_content)
        complete_user_messages.append((user_message, assistant_message))
    
    # 不完整 query
    store.save_user_message(conversation.session_id, incomplete_turn_id, "incomplete query")

    # 當前的 turn
    store.save_user_message(conversation.session_id, current_turn_id, "current query")
    store.save_assistant_message(conversation.session_id, current_turn_id, "current response")

    messages = store.load_recent_turns(conversation.session_id, current_turn_id=current_turn_id, max_turns=2)

    ordered_complete_turns = sorted(
        complete_user_messages, key=lambda turn:(turn[0].created_at, turn[0].turn_id)
        # key=lambda 建立匿名函式
    )

    # 取出預期的正確兩個 turns
    expected_turns = ordered_complete_turns[-2:]
    expected_messages = []
    for user_message, assistant_message in expected_turns:
        expected_messages.extend([user_message, assistant_message])

    assert [message.turn_id for message in messages] == [message.turn_id for message in expected_messages]
    assert [message.role for message in messages] == [message.role for message in expected_messages]
    assert [message.content for message in messages] == [message.content for message in expected_messages]

    returned_turn_ids = [message.turn_id for message in messages]
    assert incomplete_turn_id not in returned_turn_ids
    assert current_turn_id not in returned_turn_ids
    
# 檢查同一回合不能儲存重複的 role
# 寫入失敗 rollback 後 ConnectionPool 可以繼續使用
def test_store_recovers_after_duplicate_role(store:PostgresConversationHistoryStore):
    conversation = store.create_conversation()
    turn_id = uuid4()

    store.save_user_message(conversation.session_id, turn_id, "first input")

    with pytest.raises(UniqueViolation):
        store.save_user_message(conversation.session_id, turn_id, "double input")

    assistant_message = store.save_assistant_message(conversation.session_id, turn_id, "assistant response")

    assert assistant_message.role == "assistant"

def test_sessions_independent(store:PostgresConversationHistoryStore):
    first_conversation = store.create_conversation()
    second_conversation = store.create_conversation()

    first_turn_id = uuid4()
    second_turn_id = uuid4()

    store.save_user_message(first_conversation.session_id, first_turn_id, "first session query")
    store.save_assistant_message(first_conversation.session_id, first_turn_id, "first session response")
    store.save_user_message(second_conversation.session_id, second_turn_id, "second session query")
    store.save_assistant_message(second_conversation.session_id, second_turn_id, "second session response")

    # 取出存入 database 的 messages
    first_session_messages = store.load_recent_turns(
        first_conversation.session_id,
        current_turn_id=uuid4(), # 隨機產生一個 id 避開原本 function 排除最近 id 的功能
        max_turns=1
    )
    second_session_messages = store.load_recent_turns(
        second_conversation.session_id,
        current_turn_id=uuid4(),
        max_turns=1
    )

    # first_messages
    # └── ConversationMessage
    #     ├── message_id
    #     ├── session_id
    #     ├── turn_id
    #     ├── role
    #     ├── content
    #     ├── metadata
    #     └── created_at

    first_content = [message.content for message in first_session_messages]
    second_content = [message.content for message in second_session_messages]

    assert first_content == ["first session query", "first session response"]
    assert second_content == ["second session query", "second session response"]
    assert all(
        message.session_id == first_conversation.session_id
        for message in first_session_messages
    )
    assert all(
        message.session_id == second_conversation.session_id
        for message in second_session_messages
    )
