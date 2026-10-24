from llm_client import create_client, load_config
from system_orchestrator import run_system_turn
from system_state import create_system_state
from trace_utils import setup_tracer, TokenTracker # opentelemetry trace tools

from database.connection import create_connection_pool, close_connection_pool
from database.conversation_history.postgres_store import PostgresConversationHistoryStore
from session_manager import SessionManager


config, provider_config, api_key = load_config()
client = create_client(provider_config, api_key)
tracer = setup_tracer()

provider_name = config["provider"]
model = provider_config["model"]

generation = config["generation"]
parameters = {
    "model": model,
    "temperature": generation["temperature"],
    "max_tokens": generation["max_tokens"],
    "presence_penalty": generation["presence_penalty"],
}

system_state = create_system_state(parameters)
token_tracker = TokenTracker()

pool = create_connection_pool()

try:
    conversation_store = PostgresConversationHistoryStore(pool)
    session_manager = SessionManager(conversation_store)
    session_manager.initialize_current_session()

    print(f"Model Provider: {provider_name}")
    print(f"Model Name: {model}")
    print(f"Skill list: {system_state.skill.skill_ids}")
    print("Key in 'quit' while you want to end the chat.")
    print("=" * 100)

    while True:
        user_query = input("\nuser: ")
        normalized_input = user_query.strip().lower()

        if normalized_input in ("q", "quit"):
            print("system off")
            break

        if not normalized_input:
            continue

        # 執行整個系統
        response = run_system_turn(
            user_query=user_query,
            system_state=system_state,
            client=client,
            tracer=tracer,
            config=config,
            parameters=parameters,
            provider_name=provider_name,
            model=model,
            token_tracker=token_tracker,
            conversation_store=conversation_store,
            session_manager=session_manager,
        )

        token_tracker.print_usage()

        if response:
            print("=" * 100)
            print(f"user: {user_query}")
            print(f"assistant: {response}")
            print("=" * 100)

# finally 會在 try 裡的程式結束時執行
    # 包含: 使用者輸入 quit 讓 while 透過 break 結束, 程式途中發生錯誤, 對話迴圈因其他原因結束
finally:
    close_connection_pool(pool)
