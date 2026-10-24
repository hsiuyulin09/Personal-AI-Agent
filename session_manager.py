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

    def create_session(self, title:str | None = None) -> Conversation:
        conversation = self.store.create_conversation(title)
        self._current_session_id = conversation.session_id
        return conversation

    def list_sessions(self) -> list[Conversation]:
        conversation_list = self.store.list_conversations()
        return conversation_list

    def get_session(self, session_id: UUID) -> Conversation:
        self.validate_session_id(session_id)
            # 此階段只接受完整 UUID, 短 UUID 與 title 解析留給入口
        conversation = self.store.get_conversation(session_id)
        return conversation

    def switch_session(self, session_id: UUID) -> Conversation:
        conversation = self.get_session(session_id)

        if conversation is None:
            raise ValueError(f"{session_id} this session id do not exist")

        self._current_session_id = conversation.session_id
        return conversation

    def rename_session(self, session_id: UUID, title: str) -> Conversation:
        self.validate_session_id(session_id)
        conversation = self.store.rename_conversation(session_id, title)

        if conversation is None:
            raise ValueError(f"{session_id} this session id do not exist")
        return conversation

    def delete_session(self, session_id: UUID) -> bool:
        self.validate_session_id(session_id)
        deleted = self.store.delete_conversation(session_id)

        if self._current_session_id == session_id:
            replacement = self.store.get_or_create_current_conversation()
            self._current_session_id = replacement.session_id
        return deleted

    def load_session_history(self, session_id: UUID | None = None, max_turns=int | None = DEFAULT_HISTORY_TURNS) -> list[Conversation]:
        # 未指定 session_id 時讀取當前 session
        if session_id is None:
            resolved_session_id = self._current_session_id
        else:
            resolved_session_id = session_id

        self.validate_session_id(resolved_session_id)

        if max_turns is not None and (
            not isinstance(max_turns, int)
            or isinstance(max_turns, bool)
            or max_turns <= 0
        ):
            raise ValueError("max_turns must be a positive int or None")

        # 不存在和沒有歷史的 Session 都會得到空 list 因此先確認 session 存在, 避免情況無法區分
        conversation = self.store.get_conversation(resolved_session_id)
        if conversation is None:
            raise ValueError(f"session not exist (session id: {resolved_session_id})")

        conversation_history = self.load_session_history(resolved_session_id)
        return conversation_history
