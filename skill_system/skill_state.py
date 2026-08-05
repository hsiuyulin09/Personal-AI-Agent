from dataclasses import dataclass, field
from skill_system.full_table_responses import load_full_table_options
from skill_system.load_skills import format_skill_metadata_for_prompt, load_skill_metadata


@dataclass
class SkillState:
    memory: list = field(default_factory=list)
    previous_skill_id: str | None = None
    skills: list[dict] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)
    skill_metadata: str = ""
    full_table_options: list[dict] = field(default_factory=list)


def create_skill_state():
    try:
        skills = load_skill_metadata() # load 所有 skill 的 metadata
    except FileNotFoundError:
        skills = []

    skill_state = SkillState(
        skills=skills,
        skill_ids=[skill["skill_id"] for skill in skills],
        skill_metadata=format_skill_metadata_for_prompt(skills),
        full_table_options=load_full_table_options(),
    )
    return skill_state