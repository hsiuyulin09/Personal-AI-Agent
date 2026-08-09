from math import ceil
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from system_state import ContextWindowState


DEFAULT_THREAD_ID = "default"
# thread id = session_id 預留 session 空間
# 未實作 session 沒有 id 全部都用 "default"

def cjk_character(character): # 判斷是否為漢字範圍, 用於粗略估算 token 數
    judgment = (
        "\u3400" <= character <= "\u4dbf"
        or "\u4e00" <= character <= "\u9fff"
    )
    return judgment


def estimate_text_tokens(text): # 估算 token 數
    # 中文大約一個字 token*1, 其他文字以四個字元 token*1 估算
    cjk_count = sum(cjk_character(character) for character in text)
    other_count = len(text) - cjk_count
    text_tokens = cjk_count + ceil(other_count / 4) # ceil 無條件進位
    return text_tokens


def estimate_message_tokens(message): # 估算該 message 的 token 數
    message_tokens = estimate_text_tokens(str(message.get("content", ""))) + 4
    return message_tokens


def group_messages_by_turn(messages): # 對話輪次管理: 切分對話輪次
    turns = []
    current_turn = []

    for message in messages:
        if message.get("role") == "user" and current_turn:
            # 遇到 role == user 同時 current_turn 已有內容則表示該輪次結束
            turns.append(current_turn)
            current_turn = []

        current_turn.append(message)

    if current_turn: # 處理最後一輪, 不會再遇到 role == user
        turns.append(current_turn)

    return turns # list[list[dict]]


def trim_text(text, token_limit):
    # 超過單輪上限時保留內容開頭, 避免一筆過長訊息占滿 Context Window
    # 僅用於最新一輪對話就超過 token_limit 時裁切
    used_tokens = 0.0
    trimmed_characters = []

    for character in text:
        token_cost = 1 if cjk_character(character) else 0.25
        if (used_tokens + token_cost) > token_limit:
            break

        trimmed_characters.append(character)
        used_tokens += token_cost

    processed_text = "".join(trimmed_characters)

    return processed_text


def trim_oversized_turn(turn, token_limit):
    # 用 token limit 裁切最新一輪 context window token (如果僅最新一輪單輪即超過 token_limit)
    message_overhead = 4 * len(turn)
    content_limit = max(token_limit - message_overhead, 0) # 算實際 content 能用的 token 數 # 同時也是剩餘可分配 token 額度
    message_tokens = [ # 估算各 message 的 token 數
        estimate_text_tokens(str(message.get("content", "")))
        for message in turn
    ]
    message_number = len(turn) # 在單一 turn 裡的數量
    message_token_limits = [0.0] * message_number # 準備裝每則訊息的 token 上限
    message_indexes = sorted(range(message_number), key=(lambda index: message_tokens[index]))
        # range() 在每一 turn 裡產生 index 編號 # key 用於 sorted 的 parameter
        # lambda 建立小型函數 (lmbda input:output)
        # 用 token 數排序

    # 盡可能保留短 message, 未使用的 token 留給較長的 message
    for position, message_index in enumerate(message_indexes):
        remaining_message_count = len(message_indexes) - position # 計算剩餘尚未分配額度的 message 數量
        shared_token_limit = content_limit / remaining_message_count # 將剩餘可用的 content token 平分給尚未處理的 messages

        if message_tokens[message_index] <= shared_token_limit:
            message_token_limits[message_index] = message_tokens[message_index] 
                # 如果小於預設上限就把上限改成該 message_token

            content_limit -= message_tokens[message_index]
            continue

        # 最短剩餘 message 都超過共同上限時, 平均使用剩餘 token
        for remaining_index in message_indexes[position:]:
            message_token_limits[remaining_index] = shared_token_limit
        break

    oversized_turn = [ # 裁切後的結果
        {
            **message,
            "content": trim_text(str(message.get("content", "")), message_token_limits[index]),
        }
        for index, message in enumerate(turn)
    ]
    return oversized_turn


class ContextWindowManager:
    def __init__(self, max_turns=5, max_context_tokens=8000, checkpointer=None): # checkpointer 負責保存 LangGraph 的完整 State checkpoint
        if max_turns <= 0:
            raise ValueError("max_turns must be greater than 0")
        if max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be greater than 0")

        self.max_turns = max_turns
        self.max_context_tokens = max_context_tokens
        self.checkpointer = checkpointer or InMemorySaver()

        workflow = StateGraph(ContextWindowState) 
            # StateGraph() 建立一個 LangGraph workflow 指定這個流程使用 ContextWindowState 作為共用 State Schema
        workflow.add_node("context_window_manager", self.build_active_context)
            # workflow.add_node(node_name, node_function) 新增 context_window_manager node 執行時呼叫 self.build_active_context
        workflow.add_edge(START, "context_window_manager")
        workflow.add_edge("context_window_manager", END)
        self.graph = workflow.compile(checkpointer=self.checkpointer)
            # compile() 組合前面設定的 workflow 建立可執行 Grap 非執行

    def build_active_context(self, state):
        messages = state.get("messages", [])
        turns = group_messages_by_turn(messages)[-self.max_turns:]
            # 由後往前擷取 max_turns 規範的輪數
        selected_turns = []
        used_tokens = 0

        for turn in reversed(turns):
            turn_tokens = sum(estimate_message_tokens(message) for message in turn)

            if used_tokens + turn_tokens > self.max_context_tokens:
                if not selected_turns:
                    oversized_turn = trim_oversized_turn(turn, self.max_context_tokens)
                    selected_turns.append(oversized_turn)
                break # 如果加入該較舊 turn 超過 token 上限且 selected_turns 已有 turn 就不要加入目前 turn

            selected_turns.append([dict(message) for message in turn])
            used_tokens += turn_tokens

        active_context = [ # list[dict]
            message
            for turn in reversed(selected_turns)
            for message in turn
        ]

        context_state_update = { # 將拿來更新 state
            "active_context": active_context,
            "retrieved_memories": [],
            "assistant_response": None,
        }
        return context_state_update

    def prepare_context(self, user_query, thread_id=DEFAULT_THREAD_ID):
        # 接收本輪最新 user_query 並執行完整 graph # 更新 state 並輸出新的 active_context
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.invoke( # 先加入最新 query 後用 self.graph.invok 執行前面組合好的 workflow
            {
                "original_query": user_query,
                "retrieved_memories": [],
                "assistant_response": None
            },
            config
        )
        new_active_context = state.get("active_context", [])
        return new_active_context

    def save_turn(self, user_query, assistant_response, thread_id=DEFAULT_THREAD_ID):
        # assistant response -> context window manager
        # 更新 Graph State
        if not assistant_response:
            return

        config = {"configurable": {"thread_id": thread_id}}
        self.graph.update_state( # 更新 Graph State
            config,
            {
                "messages": [
                    {"role": "user", "content": user_query},
                    {"role": "assistant", "content": assistant_response},
                ],
                "original_query": user_query,
                "assistant_response": assistant_response,
            },
        )


default_context_window_manager = ContextWindowManager()
