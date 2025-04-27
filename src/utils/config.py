import yaml
from pathlib import Path

def load_config(config_path=None):
    config_path = config_path or Path(__file__).parent.parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)