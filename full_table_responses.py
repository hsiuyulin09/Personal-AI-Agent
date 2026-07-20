import json
from pathlib import Path

CURRENT_DIR = Path(__file__).parent

# json table 引導 user 的 reponse 列表 # 新增 json table 時直接在此更新即可
FULL_TABLE_DIRECT_RESPONSES = {
    
}

# 替代性回答
SUBSTITUTE_RESPONSE = "完整表格內容請至對應文件查詢。"

def load_full_table_options(skill_dir="skills"):
    options = []

    skill_root = CURRENT_DIR/skill_dir

    for table_path in sorted(skill_root.glob("*/references/*table.json")):
        table = json.loads(table_path.read_text(encoding="utf-8"))
        metadata = table["metadata"]

        options.append(
            {
                "skill_id": table_path.parents[1].name, # table_path: skills/*/references/*table.json # table_path.parents[1]: skills/*
                "full_table_type": metadata["reference_key"],
                "name": metadata["name"],
                "description": metadata["description"]
            }
        )
    return options

def full_table_hint_response(hint_result):
    response = FULL_TABLE_DIRECT_RESPONSES.get(
        hint_result.full_table_type,
        SUBSTITUTE_RESPONSE
    )
    return response