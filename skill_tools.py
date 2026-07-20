import json
import os
import subprocess
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).parent

# 每個 script 只允許固定參數，避免 LLM 自行發明參數或執行非預期操作
SCRIPT_ARGUMENT_ORDER = {
    "employee_free_ticket_points_lookup": [
        "seniority_years",
        "target_points",
    ],
    "preferential_ticket_quota_lookup": [
        "identity_group",
        "discount_type",
        "cabin",
        "employee_status",
        "seniority_months",
        "seniority_years",
    ],
    "official_seal_specification_lookup": [
        "seal_type",
        "applicable_to",
    ],
}


def run_skill_script(skill, script_id, arguments):
    # 只執行 SKILL.md 中註冊、且本檔 allowlist 有定義參數順序的 script。
    script = skill["scripts"].get(script_id)
    argument_order = SCRIPT_ARGUMENT_ORDER.get(script_id)

    if script is None or argument_order is None:
        raise ValueError(f"未註冊的 script: {script_id}")

    unknown_arguments = set(arguments) - set(argument_order)
    if unknown_arguments:
        raise ValueError(f"不支援的 script arguments: {sorted(unknown_arguments)}")

    skill_path = Path(skill["skill_path"])
    if not skill_path.is_absolute():
        skill_path = CURRENT_DIR / skill_path

    skill_root = skill_path.parent.resolve()
    script_path = (skill_root / script["path"]).resolve()

    if skill_root not in script_path.parents:
        raise ValueError("script path 不可超出 skill 目錄")

    cli_arguments = [
        "" if arguments.get(name) is None else str(arguments[name])
        for name in argument_order
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [sys.executable, str(script_path), *cli_arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        env=env,
    )

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())

    return json.loads(completed.stdout)
