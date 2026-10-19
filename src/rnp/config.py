"""Configuration loading and JSON-Schema validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .errors import ConfigError

#: Schemas live at the repository root during development and are force-included
#: into the wheel under ``rnp/schemas`` at build time (see pyproject.toml).
_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def schema_dir() -> Path:
    """Return the directory that holds the JSON Schemas."""
    packaged = Path(__file__).resolve().parent / "schemas"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    """Load ``schemas/<name>.schema.json`` (cached)."""
    if name not in _SCHEMA_CACHE:
        path = schema_dir() / f"{name}.schema.json"
        if not path.is_file():
            raise ConfigError(f"schema not found: {path}")
        _SCHEMA_CACHE[name] = json.loads(path.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE[name]


def validate_document(document: Any, schema_name: str, what: str) -> None:
    """Validate ``document`` against a schema, raising an actionable error."""
    schema = load_schema(schema_name)
    validator = jsonschema.validators.validator_for(schema)(schema)
    validator.format_checker = jsonschema.FormatChecker()
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        details = []
        for err in errors:
            location = ".".join(str(p) for p in err.absolute_path) or "<root>"
            details.append(f"{what}: {location}: {err.message}")
        raise ConfigError(f"{what} does not match {schema_name}.schema.json", details=details)


@dataclass(frozen=True)
class RunConfig:
    """A validated run configuration plus the information needed to re-run it."""

    path: Path
    raw: bytes
    data: dict[str, Any]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def base_dir(self) -> Path:
        return self.path.parent

    def resolve(self, value: str) -> Path:
        """Resolve a config path relative to the config file, not the CWD."""
        candidate = Path(value)
        return candidate if candidate.is_absolute() else (self.base_dir / candidate).resolve()

    @property
    def project(self) -> str:
        return self.data["project"]

    @property
    def species(self) -> str:
        return self.data["species"]

    @property
    def output_dir(self) -> Path:
        return self.resolve(self.data["outputs"]["dir"])

    def input_path(self, key: str) -> Path:
        return self.resolve(self.data["inputs"][key])


def load_config(path: str | Path) -> RunConfig:
    """Read, parse and validate a run config (YAML or JSON)."""
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ConfigError(f"config not found: {config_path}")
    raw = config_path.read_bytes()
    try:
        data = yaml.safe_load(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot parse config {config_path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config {config_path.name} must be a mapping")
    validate_document(data, "run", f"config {config_path.name}")
    return RunConfig(path=config_path, raw=raw, data=data)
