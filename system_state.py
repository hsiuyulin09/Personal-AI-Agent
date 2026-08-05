from dataclasses import dataclass, field
from skill_system.skill_state import SkillState, create_skill_state

@dataclass
class RagState:
    rag_metadata: list[dict] = field(default_factory=list) # default_factory=list 預設未傳入用空 list
    # 規劃 RAG metadata 用 list[dict] 處理


@dataclass
class SystemState: # 型別註記定義資料結構
    skill: SkillState
    rag: RagState
    agent_parameters: dict
    conversation_memory: list[dict] = field(default_factory=list)


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
