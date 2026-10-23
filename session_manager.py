from uuid import UUID
from database.conversation_history.store import Conversation, ConversationHistoryStore

class SessionManager:
    def __init__(self, store:ConversationHistoryStore):
        self.store = store
        self._current_session_id: UUID | None = None

    @property # 讓外部可以像讀取普通欄位一樣取得 session_id
    def current_session_id(self) -> UUID:
        if self._current_session_id is None:
            raise RuntimeError("current session has not been initialized")

        return self._current_session_id

    def initialize_current_session(self) -> Conversation:
        conversation = self.store.get_or_create_current_conversation()
            # Database 已有 Session 取得最近使用的 Session, Database 沒有 Session 建立新的 Session
        self._current_session_id = conversation.session_id

        return conversation
