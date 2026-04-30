"""Verify production-critical database indexes are present."""

from __future__ import annotations

import sys

from sqlalchemy import inspect

from cladecanvas.db import engine


REQUIRED_INDEXES: dict[str, set[str]] = {
    "nodes": {"ix_nodes_ott_id", "ix_nodes_parent_node_id"},
    "metadata": {"ix_metadata_ott_id", "ix_metadata_common_name"},
}


def missing_indexes(connection) -> dict[str, set[str]]:
    inspector = inspect(connection)
    missing: dict[str, set[str]] = {}
    for table_name, required_names in REQUIRED_INDEXES.items():
        present_names = {index["name"] for index in inspector.get_indexes(table_name)}
        table_missing = required_names - present_names
        if table_missing:
            missing[table_name] = table_missing
    return missing


def main() -> int:
    with engine.connect() as connection:
        missing = missing_indexes(connection)

    if not missing:
        print("All required CladeCanvas indexes are present.")
        return 0

    print("Missing required CladeCanvas indexes:")
    for table_name, index_names in sorted(missing.items()):
        for index_name in sorted(index_names):
            print(f"- {table_name}.{index_name}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

