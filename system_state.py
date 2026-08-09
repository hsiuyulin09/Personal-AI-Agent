from operator import add
from dataclasses import dataclass, field
from typing import Annotated, TypedDict

from skill_system.skill_state import SkillState, create_skill_state


class ContextWindowState(TypedDict, total=False): # 定義 context_window_manager LangGraph 內的資料結構
    # messages 由 LangGraph reducer 處理累加 (add)
    messages: Annotated[list[dict], add] # Annotated[資料型別, 額外資訊]
    original_query: str
    active_context: list[dict]
    retrieved_memories: list[dict]
    assistant_response: str | None

@dataclass
class RagState:
    rag_metadata: list[dict] = field(default_factory=list) # default_factory=list 預設未傳入用空 list
    # 規劃 RAG metadata 用 list[dict] 處理


@dataclass
class SystemState: # 型別註記定義資料結構
    skill: SkillState
    rag: RagState
    agent_parameters: dict


def create_rag_state(): # 暫放, RAG system 建立後會移到 RAG 目錄
    rag_state = RagState()
    return rag_state


def create_system_state(parameters):
    system_state = SystemState(
        skill=create_skill_state(),
        rag=create_rag_state(),
        agent_parameters={**parameters, "temperature": 0},
    )
    return system_state
