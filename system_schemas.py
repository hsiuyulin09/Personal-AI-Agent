from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class SystemRouteResult(StrictModel): # 使用 Pydantic 定義 (schema) 並驗證 LLM 結構化的輸出
    route: Literal["skill", "rag", "llm_chat"]
    reason: str = Field(min_length=1)
