import json


def build_llm_messages(user_query, context_window=None):
    system_prompt = "你是一名專業助理，請使用繁體中文回答使用者的問題並進行一般對話。"

    messages = [
        {"role": "system", "content": system_prompt},
        *(context_window or []), # *() 序列解包, 拆開最外層的 list
        {"role": "user", "content": user_query},
    ]
    return messages


def build_system_hint_messages(user_query, skill_metadata="", rag_metadata=None, context_window=None):
    system_prompt = """
你是系統層路由器，只負責判斷使用者問題應該交給哪一種流程處理，不要回答問題本身。

可選 route:
- skill: 使用者問題明確符合已登錄 skill metadata 的服務範圍。
- rag: 使用者問題明確需要查詢已登錄 RAG knowledge base。
- llm_chat: 一般對話、一般問答、閒聊、或沒有任何已登錄 metadata 可以可靠處理的問題。

判斷規則:
- 只能根據輸入的 skill_metadata 與 rag_metadata 判斷，不要假設未列出的能力存在。
- skill_metadata 為空時不可選 skill。
- rag_metadata 為空時不可選 rag。
- 若不確定，選 llm_chat。

請只輸出 JSON object，格式如下:
{
  "route": "skill | rag | llm_chat",
  "reason": "簡短說明判斷原因"
}
""".strip()

    prompt_data = {
        "user_query": user_query,
        "skill_metadata": skill_metadata,
        "rag_metadata": rag_metadata or [],
    }

    hint_messages = [
        {"role": "system", "content": system_prompt},
        *(context_window or []),
        {"role": "user", "content": json.dumps(prompt_data, ensure_ascii=False)}
    ]
    return hint_messages
