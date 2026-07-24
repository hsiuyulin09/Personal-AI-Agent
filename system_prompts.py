
def build_llm_messages(user_query):
    system_prompt = "你是一名專業助理，請使用繁體中文回答使用者的問題並進行一般對話。"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]
