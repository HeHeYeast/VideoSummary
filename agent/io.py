"""Schema-tolerant loaders for output/<slug>/ artifacts.

PRE-03 (Phase 1): centralizes the schema_version normalization so future
v2 migrations have a single landing point. Today all artifacts are v1;
this module exists to make tomorrow's v2 add a single switch statement
instead of a codebase-wide edit.

Behavior:
- Dict-shaped artifacts (meta.json): obj.get("schema_version", 1) — absence == v1
- List-shaped artifacts (segs.json, paragraphs.json): always treated as v1
  (top-level list cannot carry a schema_version field without breaking
  backward-compat per PROJECT.md K3 / D-04)

When v2 lands, add a migrate_to_current(obj) call inside each loader and
update the SCHEMA_VERSION constant. No call site changes.

Reference: docs/schema-versions.md
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_VERSION = 1  # current version for new artifacts; bump in v2 phase


def load_meta(path: str | Path) -> dict:
    """加载 meta.json. Dict 工件支持 schema_version 字段 (缺失则视为 v1)."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(
            f"meta.json must be a dict (v1); got {type(obj).__name__} at {path}"
        )
    # v1: schema_version absent or == 1 → no migration needed
    # future v2: insert obj = _migrate_meta(obj) here
    return obj


def load_segs(path: str | Path) -> list[dict]:
    """加载 segs.json. 顶层 list 类型, 一律视为 schema_version=1.

    历史决定 (D-04): 把 segs.json 改成 wrapped dict 即破坏老归档, 故顶层
    list 是 v1 的稳定契约; 未来 v2 如需结构升级, 由那个 phase 决定是否
    引入 wrapping (并写 migration script).
    """
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(
            f"segs.json must be a list (v1); got {type(obj).__name__} at {path}"
        )
    return obj


def load_paragraphs(path: str | Path) -> list[dict]:
    """加载 paragraphs.json. 同 load_segs, 顶层 list 即 v1."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(
            f"paragraphs.json must be a list (v1); got {type(obj).__name__} at {path}"
        )
    return obj
