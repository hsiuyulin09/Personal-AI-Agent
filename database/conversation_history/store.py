from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class Conversation: # 建立單筆 conversation schema 的單筆資料 (row) 記錄模型
    session_id: UUID
    title: str | None
    create_at: datetime
    update_at: datetime
