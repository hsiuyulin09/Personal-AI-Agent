import json
from textwrap import dedent

def format_prompt_data(data):
    # 將 Python 資料轉成保留繁體中文的 JSON 字串，方便放入 user prompt
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_context_route_messages(user_query, memory, previous_skill_id=None):
    # Context Route 判斷本次 query 是否延續上一輪
    system_prompt = dedent("""
        你是 Context Route node，請根據對話紀錄、上一輪 skill_id 與本次 user query，判斷本次 query 是否延續上一輪對話。
        只輸出一個 JSON object，不要輸出 Markdown 或其他文字。
        輸出格式：
        {
            "continuation": true,
            "reason": "75 個字以內的判斷原因"
        }

        continuation 必須是 boolean。
        reason 必須是 1 到 75 個字的 str。
        """).strip()

    route_input = {
        "previous_skill_id": previous_skill_id,
        "memory": memory,
        "user_query": user_query,
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": format_prompt_data(route_input)},
    ]


def build_hint_messages(user_query, skill_metadata, full_table_options=None):
    # Hint 只讀 metadata，判斷服務範圍並選出 skill_id
    system_prompt = dedent("""
        你是 Hint node，請根據提供的 skill metadata，判斷 user query 是否在至少一個 skill 的服務範圍內。
        若在範圍內，必須從 metadata 選出符合的 skill_id。若不在範圍內，skill_id 必須是 null。
        不要讀取或假設未提供的 skill 全文內容。
        如果 user query 是要求查看完整表格、全部表格、整張清單、完整對照表，full_table_request 必須為 true。
        如果 user query 只是查單一或數個條件、單一結果或數個結果，full_table_request 必須為 false。
        只輸出一個 JSON object，不要輸出 Markdown 或其他文字。
        輸出格式：
        {
            "scope": true,
            "skill_id": "skill-id",
            "full_table_request": false,
            "full_table_type": null,
            "reason": "75 個字以內的判斷原因"
        }

        full_table_request=true 時，full_table_type 必須從 full_table_options 的 full_table_type 選出。
        full_table_request=false 時，full_table_type 必須是 null。
        不可自行發明 full_table_type。                
        full_table_request 必須是 boolean。
        scope 必須是 boolean。
        scope=true 時: skill_id 必須是 metadata 中的 str。
        scope=false 時: skill_id 必須是 null。
        reason 必須是 1 到 75 個字的 str。
        """).strip()

    hint_input = {
        "skill_metadata": skill_metadata,
        "full_table_options": full_table_options or [],
        "user_query": user_query
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": format_prompt_data(hint_input)}
    ]


def build_resource_route_messages(user_query, full_skill, resource_index, skill_scripts, memory = None):
    # Resource Router 選擇 references 與 scripts，實際操作由 Python 執行
    system_prompt = dedent("""
        你是 Resource Router node，請根據對話紀錄、完整 skill、resource index、scripts metadata 與 user query，選出回答所需的 references 與 scripts。
        對話紀錄存在時，必須延續其中尚未完成的問題，將 memory 與本次 user query 合併理解，不可只依最後一句改變原始查詢目的。
        reference_paths 必須逐字使用 resource index 中存在的檔案名稱，不可輸出範例名稱或自行發明。
        script_id 必須逐字使用 scripts metadata 中存在的值，不可輸出範例名稱或自行發明。
        reference 路徑需相對於 skill 根目錄；index 只有檔名時，路徑前加 references/。
        從對話紀錄與 user query 整理 script arguments；缺少的參數填 null，不可自行猜測。
        不要在呼叫 script 前自行判斷條件是否足以取得單一結果；script 會根據實際表格回傳 missing_fields 或 results。
        不需要 script 時，script_calls 必須是空 list。
        只輸出一個 JSON object，不要輸出 Markdown 或其他文字。
        輸出格式：
        {
            "reference_paths": [],
            "script_calls": [],
            "reason": "75 個字以內的選擇檔案的原因"
        }

        上述空 list 僅表示輸出格式；回答需要 reference 或 script 時，必須填入輸入資料中實際存在的值。
        reason 必須是 1 到 75 個字的 str。
        """).strip()

    route_input = {
        "memory": memory or [],
        "user_query": user_query,
        "full_skill": full_skill,
        "resource_index": resource_index,
        "skill_scripts": skill_scripts,
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": format_prompt_data(route_input)},
    ]


def build_context_builder_messages(user_query, skill_id, full_skill, reference_contexts, script_results, memory=None):
    # Context Builder 讀取選中的 skill 全文，檢查資訊並萃取 Responder 所需內容。
    system_prompt = dedent("""
        你是 Context Builder node，請只依照提供的 reference_contexts、script_results、完整 skill、user query 與對話紀錄進行判斷。
        reference_contexts 與 script_results 是回答規則和數值的優先依據，不可使用外部常識取代或修改。
        如果 script_results 中 status=false 且 missing_fields 不為空，information_complete 必須是 false，missing_information 必須根據 missing_fields 與 candidate_options 組織。
        如果 script_results 中 status=false 且 result_count 大於 1，information_complete 必須是 false，並要求 user 補充能取得單一結果的欄位。
        如果 script_results 中 status=true，請優先把 results 或 quota 中的查詢結果整理到 selected_context。
        請判斷 user 是否提供足夠資訊，並萃取 Responder 回答所需的精簡 selected_context。
        只輸出一個 JSON object，不要輸出 Markdown 或其他文字。
        輸出格式：
        {
            "skill_id": "skill-id",
            "information_complete": true,
            "missing_information": [],
            "selected_context": "從 references 或 script results 萃取出的相關規則與數值",
            "reason": "75 個字以內的判斷原因"
        }

        skill_id 必須是 str。

        information_complete 為 true 時：
            - missing_information 必須是空 list。
            - selected_context 不可為空。

        information_complete 為 false 時：
            - missing_information 必須列出 user 需要補充的資訊。
            - selected_context 必須是空字串。

        selected_context 必須是 str。
        reason 必須是 1 到 75 個字的 str。
""").strip()

    trigger_input = {
        "skill_id": skill_id,
        "memory": memory or [],
        "user_query": user_query,
        "full_skill": full_skill,
        "reference_contexts": reference_contexts,
        "script_results": script_results,
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": format_prompt_data(trigger_input)},
    ]


def build_responder_messages(user_query, context_result):
    # Responder 不讀完整 skill，只根據 Context Builder 的結果組織追問或最終回答。
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
        "context_builder_result": context_result.model_dump(),
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": format_prompt_data(responder_input)},
    ]


def build_llm_messages(user_query):
    system_prompt = "你是一名專業助理，請使用繁體中文回答使用者的問題並進行一般對話。"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]
