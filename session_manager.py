from uuid import UUID
from database.conversation_history.store import Conversation, ConversationHistoryStore

# 顯示 Session 歷史時的預設回合數
DEFAULT_HISTORY_TURNS = 5


# 管理目前 Session 並透過 Store 操作 Session 資料
class SessionManager:
    def __init__(self, store:ConversationHistoryStore):
        self.store = store
        self._current_session_id: UUID | None = None

    @property # 讓外部可以像讀取普通欄位一樣取得 session_id
    def current_session_id(self) -> UUID:
        if self._current_session_id is None:
            raise RuntimeError("current session has not been initialized")
        return self._current_session_id

    @staticmethod
    def validate_session_id(session_id):
        if not isinstance(session_id, UUID):
            raise TypeError("session_id must be UUID")

    def initialize_current_session(self) -> Conversation:
        conversation = self.store.get_or_create_current_conversation()
            # Database 已有 Session 取得最近使用的 Session, Database 沒有 Session 建立新的 Session
        self._current_session_id = conversation.session_id
        return conversation

    def get_current_session(self) -> Conversation:
        conversation = self.store.get_conversation(self.current_session_id)
            # 以目前 ID 重新從 Database 取得完整 Conversation 資料        
        if conversation is NoneL
            raise RuntimeError("current session do not exist")
        return conversation
