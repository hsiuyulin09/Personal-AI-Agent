import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI
from opentelemetry.trace import Status, StatusCode


CURRENT_DIR = Path(__file__).parent


def load_config(config_path="config.yaml"):
    # 從 llm_client.py 同級目錄讀取 .env
    load_dotenv(CURRENT_DIR / ".env")

    # 若傳入的是相對路徑，就視為 llm_client.py 同級目錄底下的檔案。
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = CURRENT_DIR / config_file

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    provider_name = config["provider"]
    provider_config = config["providers"][provider_name]
    api_key = provider_config.get("api_key") or os.getenv(provider_config.get("api_key_env", ""))
    if not api_key:
        print(f"找不到 API key，請確認同級目錄 .env 內有設定 {provider_config.get('api_key_env', '')}")
        sys.exit(1) # 終止程式, 狀態碼 = 1 為異常結束狀態, 系統紀錄或開發者紀錄

    return config, provider_config, api_key


def create_client(provider_config, api_key):
    client = OpenAI(
        # OpenAI SDK 預設連到 OpenAI，用 config 指定 OpenAI-compatible endpoint
        base_url=provider_config["base_url"],
        api_key=api_key,
        # cillm_portal 需要額外 headers 才能記錄 user/platform/agent, 其他 provider 沒設定就不會帶。
        default_headers=provider_config.get("headers", {}),
    )
    return client


def call_llm(client, tracer, messages, parameters, config, node_name = None, token_tracker = None, response_format = None, result_model = None):
    with tracer.start_as_current_span("llm_generation") as span: # span 計篹 with: 區間時間
        provider_name = config["provider"]
        current_node_name = node_name or parameters["model"]

        span.set_attribute("node_name", current_node_name)
        span.set_attribute("model", parameters['model'])
        span.set_attribute("provider", provider_name)
        span.set_attribute("message_count", len(messages))
        span.set_attribute("error_type", "")
        span.set_attribute("error_message", "")
        span.set_attribute("llm_token", 0)

        try:
            request = {
                "model": parameters["model"],
                "messages": messages,
                "temperature": parameters["temperature"],
                "max_tokens": parameters["max_tokens"],
                "presence_penalty": parameters["presence_penalty"],
                "stream": False,
            }

            # 只有需要 JSON 輸出的節點才加入 response_format
            if response_format is not None:
                request["response_format"] = response_format

            response = client.chat.completions.create(**request)

            content = response.choices[0].message.content # LLM 回傳 JSON 物件內容結構範例取得回復

            span.set_attribute("input_token", response.usage.prompt_tokens)
            span.set_attribute("output_token", response.usage.completion_tokens)
            span.set_attribute("llm_token", response.usage.total_tokens)
            span.set_status(Status(StatusCode.OK))

            if token_tracker:
                token_tracker.add(response.usage.total_tokens)

            # 顯示 Evaluate
            if result_model:
                result = result_model.model_validate_json(content)
                span.set_attribute("evaluate", result.model_dump_json())
                return result

            return content

        except Exception as e:
            span.set_attribute("error_type", type(e).__name__)
            span.set_attribute("error_message", str(e))
            span.set_status(Status(StatusCode.ERROR, str(e)))
            print(f"error: {str(e)}")

            # 結構化輸出驗證失敗時保留原始例外，避免流程使用無效結果繼續執行
            if result_model:
                raise

            return None
