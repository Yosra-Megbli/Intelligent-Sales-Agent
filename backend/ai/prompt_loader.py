"""
Prompt loader.

Architecture review requirement: "no Prompt is written inside Python; every
Prompt is Markdown or YAML, under prompts/, so editing a prompt later never
touches code." This module is the only place that reads from `prompts/` -
`ai/extractor.py` and `ai/responder.py` call these helpers once at import
time and never read the filesystem themselves.

Editing a talking point, a fallback sentence, or a system prompt's wording
means editing a file under `prompts/`, not this module or its callers.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_text(relative_path: str) -> str:
    """Read a Markdown prompt file (e.g. "extractor/system.md") and return
    its raw text, trailing newline stripped."""
    path = _PROMPTS_DIR / relative_path
    return path.read_text(encoding="utf-8").rstrip("\n")


def load_yaml(relative_path: str) -> dict:
    """Read a YAML prompt-config file (e.g. "responder/talking_points.yaml")."""
    path = _PROMPTS_DIR / relative_path
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
