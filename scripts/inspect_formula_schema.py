from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mongo_formula_readonly import FormulaMongoReader


def field_paths(document: Mapping[str, Any], prefix: str = "", depth: int = 0) -> list[str]:
    paths: list[str] = []
    for key in sorted(str(value) for value in document):
        path = f"{prefix}.{key}" if prefix else key
        paths.append(path)
        value = document.get(key)
        if depth < 1 and isinstance(value, Mapping):
            paths.extend(field_paths(value, path, depth + 1))
    return paths


def main() -> int:
    with FormulaMongoReader.from_env(None, require_server_read_only=False) as reader:
        print(f"TempLab database: {reader.database_name}")
        print("TempLab collections: " + ", ".join(sorted(reader.collection_names())))
        for source_key, collection_name in sorted(reader.data_sources.items()):
            sample = reader.collection(collection_name).find_one({}, {"_id": 0}) or {}
            print(f"TempLab source {source_key}={collection_name}")
            print(f"TempLab fields {collection_name}: " + ", ".join(field_paths(sample)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
