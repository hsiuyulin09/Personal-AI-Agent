from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID


# 資料模型層
@dataclass(frozen=True) # frozen=True 表示物件建立後不能重新指定欄位 (更改欄位中的值)
class Conversation: # 建立單筆 conversation schema 的單筆資料 (row) 資料傳輸記錄模型
    session_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


# 對應 migration 內的 role CheckConstraint
# 提供給 class ConversationMessage 建立單筆資料 (row) 資料傳輸記錄模型
MessageRole = Literal["user", "assistant"]

@dataclass(frozen=True)
class ConversationMessage:
    message_id: UUID
    session_id: UUID
    turn_id: UUID
    role: MessageRole
    content: str
    metadata: Mapping[str, Any]
    created_at: datetime


# 儲存介面層
# Protocol 只定義 Conversation History 儲存層的公開契約
class ConversationHistoryStore(Protocol):
    def get_or_create_current_conversation(self) -> Conversation:
        # 預計實作功能: 先查詢最近使用的 Conversation, 如果 database 沒有任何 Conversation 就建立新的
        # Conversation 指前面的 class Conversation
        # 規定 Conversation History 必須提供一個取得或建立目前 Conversation 的方法
        # 這裡統一方法名稱、輸入與輸出, 實際查詢或建立方式由 PostgreSQL Store 實作

    def save_user_message(self, session_id: UUID, turn_id: UUID, original_query: str, metadata: Mapping[str, Any] | None = None) -> ConversationMessage:
        # original_query 未裁切的原始 user query
        # ConversationMessage 指前面的 class onversationMessage

    def load_prior_complete_turns(self, session_id: UUID, current_turn_id: UUID, max_turns: int) -> list[ConversationMessage]:
        # 提供近期歷史對話紀錄給 context window manager

    def save_assistant_message(self, session_id: UUID, turn_id: UUID, assistant_response: str, metadata: Mapping[str, Any] | None = None) -> ConversationMessage:
        # 保存 LLM response
