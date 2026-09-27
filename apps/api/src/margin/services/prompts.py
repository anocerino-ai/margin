from hashlib import sha256
from typing import Literal

from margin.config import ROOT


def load_prompt(name: Literal["classification", "blog", "linkedin"], version=None):
    version = version or ("v1" if name == "classification" else "v2")
    if (
        name not in {"classification", "blog", "linkedin"}
        or not version.startswith("v")
        or not version[1:].isdigit()
    ):
        raise ValueError("Invalid prompt reference")
    text = (ROOT / "prompts" / name / f"{version}.md").read_text()
    return text, sha256(text.encode()).hexdigest()
