"""Dynamic data loader for Unlocked schemes and documents.

Purely data-driven: reads scheme requirements and document definitions from JSON/YAML
data files. Adding a new user category (e.g. farmers, senior citizens, artisans)
requires ONLY adding a new data file under data/schemes/, without modifying any Python code.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

import yaml

from .assess import _as_scheme
from .documents import DocumentSpec, load_document_registry
from .models import SchemeRecord

log = logging.getLogger(__name__)


def _find_base_data_dir(candidates: Optional[list[Path]] = None) -> Path:
    check_paths = candidates or [
        Path("data"),
        Path(__file__).resolve().parent.parent / "data",
    ]
    for p in check_paths:
        if p.is_dir():
            return p
    return Path("data")


def load_schemes_from_file(filepath: Union[str, Path]) -> list[SchemeRecord]:
    """Load scheme records from a single JSON or YAML file."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Scheme data file not found: {path}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        raw = yaml.safe_load(text)
    else:
        raw = json.loads(text)

    schemes_data = raw.get("schemes", raw) if isinstance(raw, dict) else raw
    if not isinstance(schemes_data, list):
        raise ValueError(f"Expected list of schemes in {path}, got {type(schemes_data).__name__}")

    schemes = [_as_scheme(item) for item in schemes_data]
    log.debug("Loaded %d schemes from %s", len(schemes), path)
    return schemes


def load_schemes_by_category(
    category: str,
    base_dir: Optional[Union[str, Path]] = None,
) -> list[SchemeRecord]:
    """Load scheme records for a specific category (e.g. 'students', 'farmers', 'senior_citizens').

    Finds data/schemes/{category}.json or data/schemes/{category}.yaml.
    """
    root_data = Path(base_dir) if base_dir else _find_base_data_dir()
    schemes_dir = root_data / "schemes" if root_data.name != "schemes" else root_data

    candidates = [
        schemes_dir / f"{category}.json",
        schemes_dir / f"{category}.yaml",
        schemes_dir / f"{category}.yml",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return load_schemes_from_file(candidate)

    # Search for files with category inside
    if schemes_dir.is_dir():
        for file in schemes_dir.iterdir():
            if file.suffix.lower() in (".json", ".yaml", ".yml"):
                try:
                    text = file.read_text(encoding="utf-8")
                    data = yaml.safe_load(text) if file.suffix.lower() in (".yaml", ".yml") else json.loads(text)
                    if isinstance(data, dict) and data.get("category") == category:
                        return load_schemes_from_file(file)
                except Exception:
                    continue

    raise FileNotFoundError(f"No scheme data file found for category '{category}' in {schemes_dir}")


def list_available_categories(base_dir: Optional[Union[str, Path]] = None) -> list[str]:
    """List all user scheme categories found in data/schemes/ directory."""
    root_data = Path(base_dir) if base_dir else _find_base_data_dir()
    schemes_dir = root_data / "schemes" if root_data.name != "schemes" else root_data

    if not schemes_dir.is_dir():
        return []

    categories = []
    for file in sorted(schemes_dir.iterdir()):
        if file.suffix.lower() in (".json", ".yaml", ".yml"):
            stem = file.stem
            categories.append(stem)
    return categories


def load_all_schemes(base_dir: Optional[Union[str, Path]] = None) -> dict[str, list[SchemeRecord]]:
    """Load all schemes organized by category from data/schemes/ directory."""
    root_data = Path(base_dir) if base_dir else _find_base_data_dir()
    schemes_dir = root_data / "schemes" if root_data.name != "schemes" else root_data

    result: dict[str, list[SchemeRecord]] = {}
    if not schemes_dir.is_dir():
        return result

    for file in sorted(schemes_dir.iterdir()):
        if file.suffix.lower() in (".json", ".yaml", ".yml"):
            try:
                schemes = load_schemes_from_file(file)
                result[file.stem] = schemes
            except Exception as e:
                log.warning("Could not load schemes from %s: %e", file, e)

    return result


def load_document_definitions(filepath: Optional[Union[str, Path]] = None) -> dict[str, DocumentSpec]:
    """Load canonical document definitions from data/documents.json."""
    specs = load_document_registry(filepath)
    return {spec.id: spec for spec in specs}

