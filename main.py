from llm_client import create_client, load_config
from trace_utils import setup_tracer, TokenTracker # opentelemetry trace tools
from load_skills import load_skill_metadata, format_skill_metadata_for_prompt
from full_table_responses import load_full_table_options
from skill_orchestrator import run_agent_turn

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

print(f"Model Provider: {provider_name}")
print(f"Model Name: {model}")

memory = []
previous_skill_id = None

# load skill
skills = load_skill_metadata() # 撈出所有 SKILL.md 的 metadata (name and description)
skill_ids = [skill["skill_id"] for skill in skills] # skill list
skill_metadata = format_skill_metadata_for_prompt(skills)
full_table_options = load_full_table_options()

token_tracker = TokenTracker()
agent_parameters = {**parameters, "temperature": 0}

print(f"Skill list: {skill_ids}")
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

    response, previous_skill_id = run_agent_turn(
        user_query,
        memory,
        previous_skill_id,
        client,
        tracer,
        config,
        parameters,
        agent_parameters,
        provider_name,
        model,
        skills,
        skill_metadata,
        full_table_options,
        token_tracker,
    )
    
    token_tracker.print_usage()

    if response:
        print("=" * 100)
        print(f"user: {user_query}")
        print(f"assistant: {response}")
        print("=" * 100)
