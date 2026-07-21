from llm_client import call_llm
from trace_utils import trace_system # opentelemetry trace tools
from agent_prompts import build_context_route_messages, build_hint_messages, build_resource_route_messages, build_context_builder_messages, build_responder_messages
from skill_system.load_skills import get_skill_by_id, load_full_skill, load_skill_reference
from llm_chat import run_llm_chat_turn
from skill_system.skill_tools import run_skill_script
from skill_system.skill_models import ContextRouteResult, HintResult, ResourceRouteResult, ContextBuilderResult
from skill_system.full_table_responses import full_table_hint_response


def run_agent_turn(
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
):
    response = None
    selected_skill = None
    builder_result = None

    with trace_system(tracer, token_tracker, provider_name, model):

        if memory and previous_skill_id:
            # context_route: 判斷本次 Query 是否延續上一輪未完成的問題
            route_message = build_context_route_messages(user_query, memory, previous_skill_id)
            route_result = call_llm(client, tracer, route_message, agent_parameters, config, node_name="context_route", token_tracker=token_tracker, response_format={"type": "json_object"}, result_model=ContextRouteResult)

            if route_result.continuation: # 卻連續對話讀取前一輪的 skill_id
                selected_skill = get_skill_by_id(previous_skill_id, skills)

                if selected_skill is None:
                    raise ValueError("Cannot find last turn skill_id")
            else:
                memory.clear()
                previous_skill_id = None

        if selected_skill is None:
            # hint: 判斷服務範圍，並從所有 skills 中選出單一 skill
            hint_messages = build_hint_messages(user_query, skill_metadata, full_table_options)
            hint_result = call_llm(client, tracer, hint_messages, agent_parameters, config, node_name="hint", token_tracker=token_tracker, response_format={"type": "json_object"}, result_model=HintResult)

            if not hint_result.scope:
                response = run_llm_chat_turn(user_query, client, tracer, config, parameters, token_tracker)

            elif hint_result.full_table_request:
                response = full_table_hint_response(hint_result)
                memory.clear()
                previous_skill_id=None

            else:
                selected_skill = get_skill_by_id(hint_result.skill_id, skills)

                if selected_skill is None:
                    raise ValueError(f"Skill not exist: {hint_result.skill_id}")

        if selected_skill is not None:
            full_skill = load_full_skill(selected_skill)
            index_key = next(key for key in selected_skill["references"] if key.endswith("_index"))
            resource_index = load_skill_reference(selected_skill, selected_skill["references"][index_key]["path"])

            # resource_router: 判斷需要讀取哪些 reference，以及是否需要執行 script
            resource_messages = build_resource_route_messages(user_query, full_skill, resource_index, selected_skill["scripts"], memory=memory)
            resource_result = call_llm(client, tracer, resource_messages, agent_parameters, config, node_name="resource_router", token_tracker=token_tracker, response_format={"type": "json_object"}, result_model=ResourceRouteResult)
            reference_contexts = [
                {"path": path, "content": load_skill_reference(selected_skill, path)}
                for path in resource_result.reference_paths
            ]
            script_results = [
                {"script_id": call.script_id, "result": run_skill_script(selected_skill, call.script_id, call.arguments)}
                for call in resource_result.script_calls
            ]

            # Context Builder: 根據 User Query、SKILL.md、政策內容與 script 結果萃取回答所需的 selected_context
            context_messages = build_context_builder_messages(user_query, selected_skill["skill_id"], full_skill, reference_contexts, script_results, memory=memory)
            builder_result = call_llm(client, tracer, context_messages, agent_parameters, config, node_name="context_builder", token_tracker=token_tracker, response_format={"type": "json_object"}, result_model=ContextBuilderResult)

            # responder: 收到 selected_context 組織最終回覆
            responder_messages = build_responder_messages(user_query, builder_result)
            response = call_llm(client, tracer, responder_messages, parameters, config, node_name="responder", token_tracker=token_tracker)

    if builder_result is not None:
        if builder_result.information_complete: # information_complete 判定 True，則刪除記憶
            memory.clear()
            previous_skill_id = None

        else: # information_complete 判定 False 回傳第一輪 query/response
            memory.append({
                "role": "user",
                "content": user_query
            })
            memory.append({
                "role": "assistant",
                "content": response
            })
            previous_skill_id = selected_skill["skill_id"]

    return response, previous_skill_id
