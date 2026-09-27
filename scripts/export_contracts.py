"""Run from repository root after installing apps/api."""

import json
from pathlib import Path

from margin.api.app import create_app
from margin.config import Settings

path = Path("packages/contracts/openapi.json")
path.write_text(json.dumps(create_app(Settings(env="test")).openapi(), indent=2) + "\n")
print(path)
