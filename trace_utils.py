from contextlib import contextmanager
import json
from typing import Any
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return str(value)


EVALUATE_FIELDS = {
    "hint": {
        "scope": "service_check",
        "skill_id": "skill_selection",
        "reason": "reason",
    },
    "resource_router": {
        "reference_paths": "references_list",
        "script_calls": "script",
        "reason": "reason",
    },
    "context_builder": {
        "skill_id": "skill_id",
        "information_complete": "information_complete",
        "missing_information": "missing_information",
        "selected_context": "selected_context",
        "reason": "reason",
    },
}


def _format_evaluate_value(field_name, value):
    # script 沒有被選用時保留空白, list 與 dict 則用 JSON 保留完整結構
    if field_name == "script" and value == []:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return _format_value(value)


class TokenTracker:
    # batch_token 計算本輪所有 LLM API 回報的總 token，total_token 跨輪累積。
    def __init__(self):
        self.batch_token = 0
        self.total_token = 0

    def start_batch(self):
        self.batch_token = 0

    def add(self, llm_token):
        self.batch_token += llm_token
        self.total_token += llm_token

    def print_usage(self):
        print(f"batch_token: {self.batch_token}")
        print(f"total_token: {self.total_token}")


@contextmanager
def trace_system(tracer, token_tracker, provider, model):
    # 包住一整輪 Agent 流程，彙總所有 LLM 節點的 token 與執行時間。
    token_tracker.start_batch()

    with tracer.start_as_current_span("system") as span:
        span.set_attribute("node_name", "system")
        span.set_attribute("provider", provider)
        span.set_attribute("model", model)
        span.set_attribute("error_message", "")
        span.set_attribute("error_type", "")
        span.set_attribute("llm_token", 0)

        try:
            yield
            span.set_status(Status(StatusCode.OK))

        except Exception as error:
            span.set_attribute("error_message", str(error))
            span.set_attribute("error_type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            raise

        finally:
            # system 只顯示本輪彙總，不把相同 token 再加進 tracker。
            span.set_attribute("llm_token", token_tracker.batch_token)


class TraceTerminalExporter(SpanExporter):

    def export(self, spans):
        for span in spans:
            duration_ns = (span.end_time or 0) - (span.start_time or 0)
            duration_sec = duration_ns / 1e9 if duration_ns > 0 else 0
            node_name = span.attributes.get("node_name", span.attributes.get("model", span.name))

            print(f"\nNode_name: {node_name}")
            print("  Trace:")
            print(f"    duration: {duration_sec:.4f} 秒")
            print(f"    status: {span.status.status_code.name}")
            print("\n  Attributes:")

            for key in ["provider", "model", "error_message", "error_type", "llm_token"]:
                value = span.attributes.get(key, "")
                print(f"    {key}: {_format_value(value)}")

            evaluate_json = span.attributes.get("evaluate")
            if evaluate_json:
                evaluate = json.loads(evaluate_json)
                field_names = EVALUATE_FIELDS.get(node_name, {})

                print("\n  Evaluate:")
                for key, value in evaluate.items():
                    field_name = field_names.get(key, key)
                    print(f"    {field_name}: {_format_evaluate_value(field_name, value)}")

            print("=" * 100)

        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def setup_tracer(service_name="LLM"):
    # 初始化本地 trace，並把 span 內容直接輸出到終端
    resources = Resource(attributes={
        "service.name": service_name,
    })
    provider = TracerProvider(resource=resources)

    terminal_exporter = TraceTerminalExporter()
    terminal_processor = SimpleSpanProcessor(terminal_exporter)
    provider.add_span_processor(terminal_processor)

    tracer = provider.get_tracer(__name__)
    return tracer
