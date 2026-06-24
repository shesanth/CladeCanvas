from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from cladecanvas.schema import node_aliases


def resolve_node_id(db: Session, node_id: str, max_depth: int = 8) -> str:
    current = node_id
    seen = set()
    for _ in range(max_depth):
        if current in seen:
            break
        seen.add(current)
        try:
            row = db.execute(
                select(node_aliases.c.canonical_node_id).where(
                    node_aliases.c.alias_node_id == current
                )
            ).first()
        except SQLAlchemyError:
            return current
        if not row:
            return current
        current = row[0]
    return current


def alias_ids_for_canonical(db: Session, canonical_node_id: str) -> list[str]:
    try:
        rows = db.execute(
            select(node_aliases.c.alias_node_id).where(
                node_aliases.c.canonical_node_id == canonical_node_id
            )
        ).fetchall()
    except SQLAlchemyError:
        return []
    return [row[0] for row in rows]


def equivalent_node_ids(db: Session, node_id: str) -> tuple[str, ...]:
    canonical = resolve_node_id(db, node_id)
    ids = [canonical, *alias_ids_for_canonical(db, canonical)]
    return tuple(dict.fromkeys(ids))


def canonicalize_node_row(db: Session, row: dict) -> dict:
    parent_id = row.get("parent_node_id")
    if parent_id:
        row = {**row, "parent_node_id": resolve_node_id(db, parent_id)}
    return row


def canonicalize_node_rows(db: Session, rows: list[dict]) -> list[dict]:
    return [canonicalize_node_row(db, row) for row in rows]
