from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml

CURRENT_DIR = Path(__file__).parent
DEFAULT_SKILLS_DIR = CURRENT_DIR / "skills"

def read_text(path): # path: str
    SKILLmd_text = Path(path).read_text(encoding="utf-8")
    return SKILLmd_text # SKILLmd_text: str (full SKILL.md)

def split_front_matter(SKILLmd_text): # SKILLmd_text: str (full SKILL.md)
    # 解析 SKILL.md YAML front matter
    lines = SKILLmd_text.splitlines()
    end_index = None

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    raw_metadata = "\n".join(lines[1:end_index])
    body_text = "\n".join(lines[end_index + 1 :]).strip()
    metadata = yaml.safe_load(raw_metadata)
    
    return metadata, body_text # metadata: dict, body_text: str


def load_skill_metadata(skills_dir = DEFAULT_SKILLS_DIR):
    # 載入 skills/ 底下每個 SKILL.md 的 name 和 description
    skills_root = Path(skills_dir)

    if not skills_root.is_absolute():
        skills_root = CURRENT_DIR / skills_root

    if not skills_root.exists():
        raise FileNotFoundError(f"Skills directory not exist: {skills_root}")

    skills = []

    for skill_path in sorted(skills_root.glob("*/SKILL.md")):
        skill_id = skill_path.parent.name

        SKILLmd_text = read_text(skill_path)
        metadata, _ = split_front_matter(SKILLmd_text)

        name = str(metadata.get("name"))
        description = str(metadata.get("description"))

        skills.append(
            {
                "skill_id": skill_id,
                "name": name,
                "description": description,
                "skill_path": str(skill_path.relative_to(CURRENT_DIR)),
                "references": metadata.get("references", {}),
                "scripts": metadata.get("scripts", {})
            }
        )

    return skills # list


def load_full_skill(skill): # 讀取完整 SKILL.md  # skill: dict or str (skill_id) or Path (SKILL.md path)
    if isinstance(skill, dict):
        path = Path(skill["skill_path"])

        if not path.is_absolute():
            path = CURRENT_DIR / path

    else:
        path = Path(skill)

        if not path.suffix:
            path = DEFAULT_SKILLS_DIR / path / "SKILL.md"

        elif not path.is_absolute():
            path = CURRENT_DIR / path

    SKILLmd_text = read_text(path)

    return SKILLmd_text


def load_skill_reference(skill, reference_path):
    # 只允許讀取指定 skill 目錄內的 reference
    skill_root = (CURRENT_DIR / skill["skill_path"]).parent.resolve()
    reference_file = (skill_root / reference_path).resolve()

    if skill_root not in reference_file.parents:
        raise ValueError("reference path 不可超出 skill 目錄")

    if not reference_file.exists():
        raise FileNotFoundError(reference_file)

    return read_text(reference_file)


def format_skill_metadata_for_prompt(skills) -> str: # skills: dict
    # skill metadata 轉成 LLM routing prompt 可讀的文字
    # 僅含 name, description
    block = []

    for skill in skills:
        block.append(
            "\n".join(
                [
                    f"skill_id: {skill['skill_id']}",
                    f"name: {skill['name']}",
                    f"description: {skill['description']}",
                ]
            )
        )

    metadata_prompts = "\n\n".join(block)

    return metadata_prompts # str


def get_skill_by_id(skill_id, skills: list[dict[str, Any]]) -> dict[str, Any] | None:
    # 從 load_skill_metadata() 的結果中依 skill_id 找出指定 skill
    for skill in skills:
        if skill["skill_id"] == skill_id:
            return skill
    return None


def load_one_skill_metadata(skill_id: str, skills_dir = DEFAULT_SKILLS_DIR) -> dict[str, Any]:
    # 載入指定單一 skill 的 metadata
    # 便利函式, 讓 notebook 可以直接寫 skill = load_one_skill_metadata("hr-leave")
    skills = load_skill_metadata(skills_dir)
    skill = get_skill_by_id(skill_id, skills)
    if skill is None:
        raise ValueError(f"Skill not found: {skill_id}")
    return skill
