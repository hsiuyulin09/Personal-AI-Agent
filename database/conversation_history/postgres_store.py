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
                        # UPDATE 指定要修改的 table
                        # SET 指定欄位要更新的欄位與值
                        # WHERE 指定 (這裡用 session_id 指定) 要修改的那筆 row
                        """
                        UPDATE conversation_history.conversations
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s
                        """,
                        (session_id,)
                    )

                    save_message_row = self.row_to_message(message_row)
                    return save_message_row

    def save_user_message(self, session_id: UUID, turn_id: UUID, original_query: str, metadata: Mapping[str, Any] | None = None):
        save_user_message_row = self.save_message(session_id=session_id, turn_id=turn_id, role="user", content=original_query, metadata=metadata)
        return save_user_message_row

    def save_assistent_message(self, session_id: UUID, turn_id: UUID, assistant_response: str, metadata: Mapping[str, Any] | None = None):
        save_assistant_message_row = self.save_message(session_id=session_id, turn_id=turn_id, role="assistant", content=assistant_response, metadata=metadata)
        return save_assistant_message_row

    # 讀取近期歷史對話 (調取給 context window manager)
    def load_recent_turns(self, session_id: UUID, current_turn_id: UUID, max_turns: int):
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 0:
            raise ValueError("max_turns must be not negative int")

        if max_turns==0:
            return []

        with self.pool.connection() as connection:
            with connection.tansaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        # WITH AS 建立一個只在本次 SQL 查詢中使用的暫時查詢結果 # WITH (命名) AS (答詢內容)
                            # SELECT 選取或在查詢暫存的 table 中創造新的欄位 # 聚合函式() FILTER (WHERE 條件)
                            # WHERE turn_id <> %s 排除當輪剛進入的 user query # <> 不等於
                            # GROUP BY 邏輯分組, 非直接相鄰 (並影響理解順序的下一步 HAVING)
                        # INNER JOIN 根據指定條件，把兩個 Table 的相關 rows 連接起來, 僅保留兩邊都能配對成功的資料
                        # CASE message.role WHEN 'user' THEN 0 即為 if message.role == 'user' 就標記為 0
                        """
                        WITH recent_complete_turns AS (
                            SELECT 
                                turn_id,
                                (MIN(created_at) FILTER (WHERE role = 'user')) AS turn_started_at
                            FROM conversation_history.messages
                            WHERE
                                session_id = %s
                                AND
                                turn_id <> %s
                            GROUP BY turn_id
                            HAVING 
                                (COUNT(*) FILTER (WHERE role='user') = 1)
                                AND
                                (COUNT(*) FILTER (WHERE role='assistant') = 1)
                            ORDER BY 
                                turn_started_at DESC,
                                turn_id DESC
                            LIMIT %s
                        )
                        SELECT
                            message.message_id,
                            message.session_id,
                            message.turn_id,
                            message.role,
                            message.content,
                            message.metadata,
                            message.created_at
                        FROM conversation_history.messages AS message
                        INNER JOIN recent_complete_turns
                            ON recent_complete_turns.turn_id = message.turn_id
                        WHERE session_id = %s
                        ORDER BY
                            recent_complete_turns.turn_started_at ASC,
                            recent_complete_turns.turn_id ASC,
                            CASE message.role
                                WHEN 'user' THEN 0
                                WHEN 'assistant' THEN 1
                            END ASC,
                            message.created_at ASC,
                            message.message_id ASC

                        """,
                        (session_id, current_turn_id, max_turns, session_id)
                    )
                    rows = cursor.fetchall()

                    for row in rows:
                        complete_turns = self.row_to_message(row)

        return complete_turns
