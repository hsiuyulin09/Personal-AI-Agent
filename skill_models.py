from pydantic import BaseModel, ConfigDict, Field, model_validator

# Hint LLM 判斷不在服務範圍時，由 Python 直接回傳，避免呼叫 Responder LLM。
OUT_OF_SCOPE_MESSAGE = "此問題非本系統服務範圍，請重新提問"


class StrictModel(BaseModel):
    # 嚴格驗證型別，並禁止 LLM 回傳 schema 以外的欄位。
    model_config = ConfigDict(strict=True, extra="forbid")


class ContextRouteResult(StrictModel):
    # Context Route LLM: 判斷本次 query 是否延續上一輪對話
    continuation: bool
    reason: str = Field(min_length=1)


class HintResult(StrictModel):
    # Hint LLM: 判斷服務範圍，並從 metadata 選出單一 skill
    scope: bool
    skill_id: str | None
    full_table_request: bool
    full_table_type: str | None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_skill_selection(self):
        # 在服務範圍內時必須選出 skill，不在範圍內時不可選 skill
        if self.scope and not self.skill_id:
            raise ValueError("scope=true 時，skill_id 不可為空")

        if not self.scope and self.skill_id is not None:
            raise ValueError("scope=false 時，skill_id 必須為 null")
        
        if not self.scope and self.full_table_request:
            raise ValueError("scope=false 時，full_table_request 必須是 false")
        
        if self.full_table_request and not self.full_table_type:
            raise ValueError("full_table_request=true 時，full_table_type 不可為空")

        if not self.full_table_request and self.full_table_type is not None:
            raise ValueError("full_table_request=false 時，full_table_type 必須是 null")

        return self


class ScriptCall(StrictModel):
    script_id: str
    arguments: dict[str, str | int | None]


class ResourceRouteResult(StrictModel):
    # Resource Router LLM: 選出本次回答需要的 references 與 scripts
    reference_paths: list[str]
    script_calls: list[ScriptCall]
    reason: str = Field(min_length=1)


class ContextBuilderResult(StrictModel):
    # Context Builder LLM: 讀取選中的 skill，萃取 context 並檢查資訊是否足夠，回傳 missing_information 或 information_complete
    skill_id: str = Field(min_length=1)
    information_complete: bool
    missing_information: list[str]
    selected_context: str
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_information_status(self):
        # 資訊足夠時，不應再列出缺少資訊
        if self.information_complete and self.missing_information:
            raise ValueError("information_complete=true 時，missing_information 必須為空 list")

        # 資訊不足時，必須明確列出需要 user 補充的內容
        if not self.information_complete and not self.missing_information:
            raise ValueError("information_complete=false 時，missing_information 不可為空 list")

        # 資訊足夠時必須提供 Responder 所需的精簡 context
        if self.information_complete and not self.selected_context.strip():
            raise ValueError("information_complete=true 時，selected_context 不可為空")

        # 資訊不足時 Responder 只需要 missing_information，不傳 skill context
        if not self.information_complete and self.selected_context:
            raise ValueError("information_complete=false 時，selected_context 必須為空字串")

        return self
