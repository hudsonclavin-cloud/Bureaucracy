from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, TypeVar


T = TypeVar("T")


def load_json_file(path: str | Path, *, default_factory: Callable[[], T]) -> T:
    file_path = Path(path)
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default_factory()


def write_json_file(path: str | Path, payload: Any, *, compact: bool = False) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None

    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(output_path.parent),
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(
            payload,
            handle,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
            ensure_ascii=False,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    try:
        os.replace(temp_path, output_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)

    return output_path


def replace_file(source_path: str | Path, destination_path: str | Path) -> Path:
    source = Path(source_path)
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)
    return destination


def remove_file(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)
