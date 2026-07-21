from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILL_CONFIG_PATH = PROJECT_ROOT / "configs" / "skill_config.yaml"


def load_skill_config(config_path=DEFAULT_SKILL_CONFIG_PATH):
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = PROJECT_ROOT / config_file

    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}