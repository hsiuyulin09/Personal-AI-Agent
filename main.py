from llm_client import create_client, load_config
from system_orchestrator import run_system_turn
from system_state import create_system_state
from trace_utils import setup_tracer, TokenTracker # opentelemetry trace tools

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

print(f"Model Provider: {provider_name}")
print(f"Model Name: {model}")
print(f"Skill list: {system_state.skill.skill_ids}")
print("Key in 'quit' while you want to end the chat.")
print("assistant: 您好，很高興見到您。您有任何問題需要協助嗎？")
print("=" * 100)

while True:
    user_query = input("\nuser: ").strip()

    if user_query.lower() in ["q", "quit"]:
        print("system off")
        break

    if not user_query:
        continue

    response = run_system_turn(user_query, system_state, client, tracer, config, parameters, provider_name, model, token_tracker)
        # 執行整個系統

    token_tracker.print_usage()

    if response:
        print("=" * 100)
        print(f"user: {user_query}")
        print(f"assistant: {response}")
        print("=" * 100)
