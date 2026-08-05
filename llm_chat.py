from system_set_prompts import build_llm_messages
from llm_client import call_llm


def run_llm_chat_turn(user_query, client, tracer, config, parameters, token_tracker, conversation_memory=None):
    llm_messages = build_llm_messages(user_query, conversation_memory)
    response = call_llm(client, tracer, llm_messages, parameters, config, node_name="llm_chat", token_tracker=token_tracker)
    return response
