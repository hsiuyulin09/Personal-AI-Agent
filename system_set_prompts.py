import json
from textwrap import dedent


def format_prompt_data(data):
    # 將 Python 資料轉成保留繁體中文的 JSON 字串，方便放入 user prompt
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_llm_messages(user_query, context_window=None):
    system_prompt = "你是一名專業助理，請使用繁體中文回答使用者的問題並進行一般對話。"

    messages = [
        {"role": "system", "content": system_prompt},
        *(context_window or []), # *() 序列解包, 拆開最外層的 list
        {"role": "user", "content": user_query},
    ]
    return messages


def build_system_hint_messages(user_query, skill_metadata="", rag_metadata=None, context_window=None):
    system_prompt = dedent("""
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
        """).strip()

    hint_input = {
        "user_query": user_query,
        "skill_metadata": skill_metadata,
        "rag_metadata": rag_metadata or [],
    }

    hint_messages = [
        {"role": "system", "content": system_prompt},
        *(context_window or []),
        {"role": "user", "content": format_prompt_data(hint_input)}
    ]
    return hint_messages


def build_responder_messages(user_query, context_result):
    # Responder 根據 Context Builder 的結果組織回答
    system_prompt = dedent("""
        你是 Responder node，請使用繁體中文，根據 Context Builder 的結果回覆 user。

        information_complete 為 false 時：
            - 根據 missing_information 禮貌且清楚地要求 user 補充資料。
            - 不可自行回答尚未具備足夠資訊的問題。

        information_complete 為 true 時：
            - 只根據 selected_context 組織最終答案。
            - 不可增加 selected_context 沒有提供的規則。
            - 不可自行加入 selected_context 沒有的括號補充或分類標籤。
            - selected_context 有明確答案時直接回答，不可改用外部常識或要求 user 另行確認。

        直接輸出給 user 閱讀的自然語言，不要輸出 JSON、Markdown code block 或內部判斷過程。
        """).strip()

    responder_input = {
        "user_query": user_query,
        "context_builder_result": context_result.model_dump()
    }

    responder_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": format_prompt_data(responder_input)},
    ]
    return responder_messages