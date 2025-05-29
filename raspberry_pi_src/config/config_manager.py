import json
import os


BASE = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE, "config.json")

def _load() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

# config.py (add this to the bottom)
def save():
    """Write the current settings dict back to the json file"""
    with open(CONFIG_PATH, "w") as f:
        json.dump(settings, f, indent=2)

# module‐level "singleton" config dict (one instance of settings shared between models)
settings: dict = _load()
