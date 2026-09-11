from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from database.conversation_history.store import Conversation, ConversationMessage, MessageRole


class PostgresConversationHistoryStore:
    def __init__(self, pool: ConnectionPool):
        # 預計接收由 database.connection 建立的共用 ConnectionPool
        self.pool = pool

    def row_to_conversation(self, row: Mapping[str, Any]):
        # 將 conversations table 的一筆 row 轉成 Conversation
        conversation_row = Conversation(
            session_id=row["session_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
        return conversation_row

    def row_to_message(self, row: Mapping[str, Any]):
        # 將 messages table 的一筆 row 轉成 ConversationMessage
        role = row["role"]
        if role not in ("user", "assistant"):
            raise ValueError(f"unavailable message role return from database: {role!r}")

        metadata = row["metadata"]
        if not isinstance(metadata, Mapping):
            raise ValueError("message metadata returned by database must be a JSON object")

        message_row = ConversationMessage(
            message_id=row["message_id"],
            session_id=row["session_id"],
            turn_id=row["turn_id"],
            role=role,
            content=row["content"],
            metadata=metadata,
            created_at=row["created_at"]
        )
        return message_row

    def get_or_create_current_conversation(self):
        with self.pool.connection() as connection:
            # .connection() 從 pool (connection pool) 取得一條 database 連線
            with connection.transaction():
                # 使用取得的 connection 建立一個 transaction 範圍 (正常: commit, 失敗: rollback)
                with connection.cursor(row_factory=dict_row) as cursor:
                    # .cursor() 建立可執行 SQL 指令、傳入參數和讀取結果的 cursor
                    # dict_row 回傳內容透過 row_factory 轉成 dict 格式
                    cursor.execute(
                        """
                        SELECT session_id, title, created_at, updated_at
                        FROM conversation_history.conversations
                        ORDER BY updated_at DESC
                        LIMIT 1
                        """
                    )

                    row = cursor.fetchone()
                    # 存在 session 時直接讀取最新 update 的 session
                    if row is not None:
                        conversation_row = self.row_to_conversation(row)
                        return conversation_row

                    session_id = uuid4() # 產生隨機十六進位 32 碼 uuid
                    cursor.execute(
                        # INSERT INTO 向資料表新增一筆 row
                        # VALUES 對應 INSERT INTO 的欄位順序新增到資料表中
                        # RETURNING 將指定 (目前新增的一筆) 欄位資料回傳
                        """
                        INSERT INTO conversation_history.conversations (session_id, title, created_at, updated_at)
                        VALUES (%s, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        RETURNING session_id, title, created_at, updated_at
                        """,
                        (session_id,)
                    )

                    create_row = cursor.fetchone() # fetchone() 從 cursor 的站存查詢結果中取出 row
                    if create_row is None:
                        raise RuntimeError("conversation was created but no row was returned")

                    conversation_row = self.row_to_conversation(create_row)
                    return conversation_row

    def save_message(self, session_id: UUID, turn_id: UUID, role: MessageRole, content: str, metadata: Mapping[str, Any] | None = None):
        # 保存 user or assistent message 的內部共用 function
        if role not in ("user", "assistant"):
            raise ValueError(f"unavailable message role: {role!r}")

        if not isinstance(content, str):
            raise TypeError("message content type must be string")

        if metadata is None:
            resolve_metadata: dict[str, Any] = {}
        else:
            if not isinstance(metadata, Mapping):
                raise TypeError("metadata type must be Mapping")
            resolve_metadata = dict(metadata)

        message_id = uuid4()

        with self.pool.connection() as connection:
            with connection.transction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO conversation_history.messages (message_id, session_id, turn_id, role, content, metadata, created_at)
                        VALUES (%S, %S, %S, %S, %S, %S, CURRENT_TIMESTAMP)
                        RETURNING message_id, session_id, turn_id, role, content, metadata, created_at
                        """,
                        (message_id, session_id, turn_id, role, content, Jsonb(resolve_metadata))
                    )

                    message_row = cursor.fetchone()

                    if message_row is None:
                        raise RuntimeError("message was created but no row was returned")

                    cursor.execute(
                        """
                        UPDATE conversation_history.conversations
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s
                        """,
                        (session_id,)
                    )

                    row = self.row_to_message(message_row)
                    return row
