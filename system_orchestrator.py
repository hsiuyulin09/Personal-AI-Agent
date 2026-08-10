from context_window_manager import DEFAULT_THREAD_ID, default_context_window_manager
from llm_chat import run_llm_chat_turn
from llm_client import call_llm
from system_schemas import SystemHintResult
from system_set_prompts import build_system_hint_messages, build_responder_messages
from trace_utils import trace_system
from skill_system.skill_orchestrator import run_skill_agent_turn


def has_registered_skills(system_state): # 檢查 skill metadata list 有無內容
    return bool(system_state.skill.skills) 


def has_registered_rag(system_state): # 檢查 RAG metadata list 有無內容
    return bool(system_state.rag.rag_metadata)


def run_system_hint(user_query, context_window, system_state, client, tracer, config, token_tracker):
    # 判斷要走 RAG, skill 或直接走 LLM
    if not has_registered_skills(system_state) and not has_registered_rag(system_state):
        # 若 RAG, Skill 清單為空直接走普通 llm_chat
        system_route_result = SystemHintResult(route="llm_chat", reason="No skill or RAG metadata registered.")
        return system_route_result

    hint_messages = build_system_hint_messages(user_query=user_query, skill_metadata=system_state.skill.skill_metadata, rag_metadata=system_state.rag.rag_metadata, context_window=context_window)
    hint_result = call_llm(client, tracer, hint_messages, system_state.agent_parameters, config, node_name="system_hint", token_tracker=token_tracker, response_format={"type": "json_object"}, result_model=SystemHintResult)

    if hint_result.route == "skill" and not has_registered_skills(system_state):
        # hint 判定走 skill 但 skill 清單內為空
        hint_result = SystemHintResult(
            route="llm_chat",
            reason="System hint selected skill, but no skills are registered.",
        )
        return hint_result

    if hint_result.route == "rag" and not has_registered_rag(system_state):
        # hint 判定走 rag 但 rag 清單內為空
        hint_result = SystemHintResult(
            route="llm_chat",
            reason="System hint selected RAG, but no RAG metadata is registered."
        )
        return hint_result

    return hint_result


def run_responder(user_query, context_result, client, tracer, config, parameters, token_tracker):
    # Responder 取得 Context Builder 結果並組織 Skill 和 RAG 的最終回答
    responder_messages = build_responder_messages(user_query, context_result)
    response = call_llm(client, tracer, responder_messages, parameters, config, node_name = "responder", token_tracker = token_tracker)
    return response


def run_skill_turn(user_query, context_window, system_state, client, tracer, config, parameters, provider_name, model, token_tracker):
    # system_state 以封裝形式傳入再轉換成 run_skill_agent_turn() 的呼叫參數
    response = run_skill_agent_turn(
        user_query=user_query,
        context_window=context_window,
        client=client,
        tracer=tracer,
        config=config,
        parameters=parameters,
        agent_parameters=system_state.agent_parameters,
        provider_name=provider_name,
        model=model,
        skills=system_state.skill.skills,
        skill_metadata=system_state.skill.skill_metadata,
        full_table_options=system_state.skill.full_table_options,
        token_tracker=token_tracker,
        manage_trace=False,
    )

    return response


def run_rag_turn(user_query, context_window, system_state, client, tracer, config, parameters, token_tracker):
    try:
        from rag_orchestrator import run_rag_agent_turn

    except ModuleNotFoundError: # rag 錯誤時直接走一般聊天 LLM
        response = run_llm_chat_turn(user_query, client, tracer, config, parameters, token_tracker, context_window)
        return response

    response = run_rag_agent_turn(user_query=user_query, context_window=context_window, rag_state=system_state.rag, client=client, tracer=tracer, config=config, parameters=parameters, token_tracker=token_tracker)
    # 引入並走完整的 RAG system 的流程
    return response


def run_system_turn(user_query, system_state, client, tracer, config, parameters, provider_name, model, token_tracker, context_manager=default_context_window_manager, thread_id=DEFAULT_THREAD_ID):
    # 實際系統流程
    with trace_system(tracer, token_tracker, provider_name, model):
        context_window = context_manager.prepare_context(user_query, thread_id)
            # Context Window Manager 裁切取得 context window

        hint_result = run_system_hint(user_query, context_window, system_state, client, tracer, config, token_tracker)
            # system hinter 判斷應往 RAG system or Skill system

        if hint_result.route == "skill":
            response = run_skill_turn(user_query, context_window, system_state, client, tracer, config, parameters, provider_name, model, token_tracker)
             # 走 skill system

        elif hint_result.route == "rag":
            response = run_rag_turn(user_query, context_window, system_state, client, tracer, config, parameters, token_tracker)
                # 走 RAG system

        elif hint_result.route == "llm_chat":
            response = run_llm_chat_turn(user_query, client, tracer, config, parameters, token_tracker, context_window)
                # 非 RAG system, Skill system 直接走一般 LLM Chat

        else:
            raise ValueError(f"Unknown system route: {hint_result.route}")
            # hinter 輸出 route 結果有問題 (實際應該在 pydantic 就被阻擋)

        if response:
            context_manager.save_turn(user_query, response, thread_id)
                # 三條 route 的回答統一交回 Context Window Manager 保存

        return response
