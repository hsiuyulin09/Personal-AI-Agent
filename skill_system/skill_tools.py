import json
import os
import subprocess
import sys
from pathlib import Path

from skill_system.skill_config import load_skill_config


CURRENT_DIR = Path(__file__).parent

# 每個 script 只允許固定參數，避免 LLM 自行發明參數或執行非預期操作
SKILL_CONFIG = load_skill_config()
SCRIPT_ARGUMENT_ORDER = SKILL_CONFIG.get("script_argument_order", {})
SCRIPT_TIMEOUT_SECONDS = SKILL_CONFIG.get("script_timeout_seconds", 10)


#
def get_script_prompt_metadata(skill_scripts):
    # 將 config 中的參數白名單一起交給 Resource Router，避免模型自行發明 arguments key。
    return {
        script_id: {
            **metadata,
            "allowed_arguments": SCRIPT_ARGUMENT_ORDER.get(script_id, []),
        }
        for script_id, metadata in skill_scripts.items()
    }


#
def _json_argument(value, argument_name):
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{argument_name} 必須是可序列化的 JSON") from error
    return value


#
def _normalize_script_arguments(argument_order, arguments):
    resolved_arguments = dict(arguments)

    # 單一 payload script 可接受模型展開的 JSON object，再由目標 script 驗證內部欄位。
    if argument_order == ["payload"] and "payload" not in resolved_arguments:
        resolved_arguments = {"payload": resolved_arguments}

    unknown_arguments = set(resolved_arguments) - set(argument_order)
    if unknown_arguments:
        raise ValueError(f"不支援的 script arguments: {sorted(unknown_arguments)}")

    normalized_arguments = {}
    for name in argument_order:
        value = _json_argument(resolved_arguments.get(name), name)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (str, int))
        ):
            raise ValueError(f"script argument {name} 必須是字串、整數或 null")
        normalized_arguments[name] = value

    return normalized_arguments

def run_skill_script(skill, script_id, arguments):
    # 只執行 SKILL.md 中註冊、且本檔 allowlist 有定義參數順序的 script。
    script = skill["scripts"].get(script_id)
    argument_order = SCRIPT_ARGUMENT_ORDER.get(script_id)

    if script is None or argument_order is None:
        raise ValueError(f"未註冊的 script: {script_id}")

    normalized_arguments = _normalize_script_arguments(argument_order, arguments)

    skill_path = Path(skill["skill_path"])
    if not skill_path.is_absolute():
        skill_path = CURRENT_DIR / skill_path

    skill_root = skill_path.parent.resolve()
    script_path = (skill_root / script["path"]).resolve()

    if skill_root not in script_path.parents:
        raise ValueError("script path 不可超出 skill 目錄")

    cli_arguments = [
        "" if normalized_arguments[name] is None else str(normalized_arguments[name])
        for name in argument_order
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [sys.executable, str(script_path), *cli_arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=SCRIPT_TIMEOUT_SECONDS,
        env=env,
    )

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())

    return json.loads(completed.stdout)
