from contextlib import nullcontext
from llm_client import call_llm
from trace_utils import trace_system # opentelemetry trace tools
from skill_system.skill_prompts import build_hint_messages, build_resource_route_messages, build_context_builder_messages
from skill_system.load_skills import get_skill_by_id, load_full_skill, load_skill_reference
from skill_system.skill_tools import run_skill_script
from skill_system.skill_schemas import HintResult, ResourceRouteResult, ContextBuilderResult
from skill_system.full_table_responses import full_table_hint_response


def run_skill_agent_turn(user_query, context_window, client, tracer, config, agent_parameters, provider_name, model, skills, skill_metadata, full_table_options, token_tracker, manage_trace=True):
    context_result  = None
    selected_skill = None

    trace_context = trace_system(tracer, token_tracker, provider_name, model) if manage_trace else nullcontext()

    with trace_context:

        if selected_skill is None:
            # hint: 判斷服務範圍，並從所有 skills 中選出單一 skill
            hint_messages = build_hint_messages(user_query, skill_metadata, full_table_options, context_window)
            hint_result = call_llm(client, tracer, hint_messages, agent_parameters, config, node_name="hint", token_tracker=token_tracker, response_format={"type": "json_object"}, result_model=HintResult)

            if not hint_result.scope:
                raise ValueError("Skill Hinter found no matching skill.")

            elif hint_result.full_table_request:
                skill_id=hint_result.skill_id
                selected_context=full_table_hint_response(hint_result)

                context_result = ContextBuilderResult(skill_id=skill_id, information_complete=True, missing_information=[], selected_context=selected_context, reason="使用已設定的完整表格替代回答。")

            else:
                selected_skill = get_skill_by_id(hint_result.skill_id, skills)

                if selected_skill is None:
                    raise ValueError(f"Skill not exist: {hint_result.skill_id}")

        if selected_skill is not None:
            full_skill = load_full_skill(selected_skill)
            index_key = next(key for key in selected_skill["references"] if key.endswith("_index"))
            resource_index = load_skill_reference(selected_skill, selected_skill["references"][index_key]["path"])

            # resource_router: 判斷需要讀取哪些 reference，以及是否需要執行 script
            resource_messages = build_resource_route_messages(user_query, full_skill, resource_index, selected_skill["scripts"], context_window)
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
            context_messages = build_context_builder_messages(user_query, selected_skill["skill_id"], full_skill, reference_contexts, script_results, context_window)
            context_result = call_llm(client, tracer, context_messages, agent_parameters, config, node_name="context_builder", token_tracker=token_tracker, response_format={"type": "json_object"}, result_model=ContextBuilderResult)

    if context_result is None:
        raise RuntimeError("Skill System did not produce Context Builder result.")

    return context_result
