from __future__ import annotations

import json
import os
from typing import Any

from .base import Skill


def load_skill_from_json(path: str) -> Skill:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return Skill(
        name=data["name"], description=data.get("description", ""),
        system_prompt=data.get("system_prompt", ""),
        knowledge_files=data.get("knowledge_files", []),
        metadata=data.get("metadata", {}), enabled=data.get("enabled", True),
    )


def load_skill_from_yaml(path: str) -> Skill:
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required to load YAML skills. Install it with: pip install pyyaml")
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return Skill(
        name=data["name"], description=data.get("description", ""),
        system_prompt=data.get("system_prompt", ""),
        knowledge_files=data.get("knowledge_files", []),
        metadata=data.get("metadata", {}), enabled=data.get("enabled", True),
    )


def load_skill(path: str) -> Skill:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        return load_skill_from_yaml(path)
    if ext == ".json":
        return load_skill_from_json(path)
    raise ValueError(f"Unsupported skill file format: {ext}. Use .json or .yaml")


def load_skills_from_directory(directory: str) -> list[Skill]:
    skills: list[Skill] = []
    if not os.path.isdir(directory):
        return skills
    for fname in sorted(os.listdir(directory)):
        if fname.endswith((".json", ".yaml", ".yml")):
            try:
                skills.append(load_skill(os.path.join(directory, fname)))
            except Exception as exc:
                print(f"Warning: failed to load skill '{fname}': {exc}")
    return skills
