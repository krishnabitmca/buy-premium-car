from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from datetime import date
import yaml

@dataclass
class Settings:
    market: dict
    output: dict
    search: dict
    network: dict

def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_settings(path: str | Path) -> Settings:
    raw = load_yaml(path)
    for key in ("market","output","search","network"):
        raw.setdefault(key,{})
    if not raw["market"].get("reference_date"):
        raw["market"]["reference_date"]=date.today().isoformat()
    return Settings(**raw)