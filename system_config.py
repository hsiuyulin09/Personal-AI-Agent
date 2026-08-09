from pathlib import Path
import yaml


PROJECT_DIR = Path(__file__).resolve().parent 
    # __file__ 本檔案所在路徑
    # .resolve() 整理成完整絕對路徑
    # .parent 取得所在的資料夾
SYSTEM_CONFIG_PATH = PROJECT_DIR / "configs" / "system_config.yaml"


def load_system_config(path=SYSTEM_CONFIG_PATH):
    config_file = Path(path)

    with open(config_file, "r", encoding="utf-8") as file:
        system_config = yaml.safe_load(file) or {}

    if not isinstance(system_config, dict):
        raise ValueError("system_config.yaml must contain a mapping")

    return system_config
