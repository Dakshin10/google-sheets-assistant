"""
Tests for the incremental sync engine:
- Row hash computation
- Primary key detection
- Change detection (inserts, updates, soft deletes)
"""
import json
import pytest
import pandas as pd

from services.sync_engine import (
    compute_row_hash,
    detect_primary_key,
    parse_spreadsheet_id,
)


# ─── Utilities ─────────────────────────────────────────────────────────────────

def test_compute_row_hash_stable():
    """Same dict always produces the same hash."""
    row = {"id": 1, "name": "Apple", "price": 1.5}
    h1 = compute_row_hash(row)
    h2 = compute_row_hash(row)
    assert h1 == h2


def test_compute_row_hash_different_values():
    """Different values produce different hashes."""
    h1 = compute_row_hash({"id": 1, "name": "Apple"})
    h2 = compute_row_hash({"id": 1, "name": "Banana"})
    assert h1 != h2


def test_compute_row_hash_key_order_irrelevant():
    """Dict key order does not affect the hash (sorted internally)."""
    h1 = compute_row_hash({"a": 1, "b": 2})
    h2 = compute_row_hash({"b": 2, "a": 1})
    assert h1 == h2


def test_parse_spreadsheet_id_valid():
    url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit"
    assert parse_spreadsheet_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"


def test_parse_spreadsheet_id_invalid():
    with pytest.raises(ValueError):
        parse_spreadsheet_id("https://google.com")


# ─── Primary Key Detection ─────────────────────────────────────────────────────

def test_detect_primary_key_id_column():
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Carol"],
        "price": [10.0, 20.0, 30.0]
    })
    assert detect_primary_key(df) == "id"


def test_detect_primary_key_uuid_column():
    df = pd.DataFrame({
        "uuid": ["aaa-111", "bbb-222", "ccc-333"],
        "name": ["Alice", "Bob", "Carol"]
    })
    assert detect_primary_key(df) == "uuid"


def test_detect_primary_key_no_unique_column():
    """Returns None when no suitable unique ID column exists."""
    df = pd.DataFrame({
        "product": ["Apple", "Banana", "Apple"],
        "price": [1.0, 2.0, 1.0]
    })
    assert detect_primary_key(df) is None


def test_detect_primary_key_non_unique_id():
    """An 'id' column with duplicates should NOT be used as primary key."""
    df = pd.DataFrame({
        "id": [1, 1, 2],
        "name": ["Alice", "Alice Copy", "Bob"]
    })
    assert detect_primary_key(df) is None


# ─── Change Detection (Pure Logic) ────────────────────────────────────────────

def _make_snapshot(rows: list[dict], spreadsheet_id="sid", title="sheet1") -> dict:
    """Simulates the prev_snapshots dict from a list of row dicts."""
    result = {}
    for idx, row in enumerate(rows, start=1):
        rh = compute_row_hash(row)
        result[idx] = {
            "row_index": idx,
            "row_hash": rh,
            "row_data": json.dumps(row)
        }
    return result


def _make_current_rows(df: pd.DataFrame) -> list[dict]:
    """Simulates the current_rows list built in sync_worksheet."""
    current_rows = []
    for idx, row in df.iterrows():
        row_index = idx + 1
        row_dict = row.to_dict()
        row_hash = compute_row_hash(row_dict)
        current_rows.append({"row_index": row_index, "row_hash": row_hash, "row_dict": row_dict})
    return current_rows


def _detect_changes(current_rows: list, prev_snapshots: dict):
    """Pure re-implementation of the index-based change detection from sync_worksheet."""
    inserts, updates, deletes = [], [], []
    max_len = max(len(current_rows), len(prev_snapshots)) if prev_snapshots else len(current_rows)
    for i in range(1, max_len + 1):
        curr_exists = i <= len(current_rows)
        prev_exists = i in prev_snapshots
        if curr_exists and not prev_exists:
            inserts.append(current_rows[i - 1])
        elif curr_exists and prev_exists:
            curr_r = current_rows[i - 1]
            prev_s = prev_snapshots[i]
            if curr_r["row_hash"] != prev_s["row_hash"]:
                curr_r["old_row_index"] = i
                updates.append(curr_r)
        elif not curr_exists and prev_exists:
            deletes.append(i)
    return inserts, updates, deletes


def test_change_detection_all_same():
    rows = [{"id": 1, "name": "Apple"}, {"id": 2, "name": "Banana"}]
    df = pd.DataFrame(rows)
    prev = _make_snapshot(rows)
    curr = _make_current_rows(df)
    inserts, updates, deletes = _detect_changes(curr, prev)
    assert inserts == []
    assert updates == []
    assert deletes == []


def test_change_detection_new_row():
    prev_rows = [{"id": 1, "name": "Apple"}]
    curr_rows_data = [{"id": 1, "name": "Apple"}, {"id": 2, "name": "Banana"}]
    df = pd.DataFrame(curr_rows_data)
    prev = _make_snapshot(prev_rows)
    curr = _make_current_rows(df)
    inserts, updates, deletes = _detect_changes(curr, prev)
    assert len(inserts) == 1
    assert inserts[0]["row_dict"]["id"] == 2
    assert updates == []
    assert deletes == []


def test_change_detection_updated_row():
    prev_rows = [{"id": 1, "name": "Apple"}, {"id": 2, "name": "Banana"}]
    curr_rows_data = [{"id": 1, "name": "Apple"}, {"id": 2, "name": "BlueBerry"}]
    df = pd.DataFrame(curr_rows_data)
    prev = _make_snapshot(prev_rows)
    curr = _make_current_rows(df)
    inserts, updates, deletes = _detect_changes(curr, prev)
    assert inserts == []
    assert len(updates) == 1
    assert updates[0]["row_dict"]["name"] == "BlueBerry"
    assert deletes == []


def test_change_detection_deleted_row():
    prev_rows = [{"id": 1, "name": "Apple"}, {"id": 2, "name": "Banana"}]
    curr_rows_data = [{"id": 1, "name": "Apple"}]  # row 2 removed
    df = pd.DataFrame(curr_rows_data)
    prev = _make_snapshot(prev_rows)
    curr = _make_current_rows(df)
    inserts, updates, deletes = _detect_changes(curr, prev)
    assert inserts == []
    assert updates == []
    assert len(deletes) == 1
    assert deletes[0] == 2  # row_index 2 marked for soft delete


def test_change_detection_mixed():
    """Simultaneously tests update and delete in a single index-based run."""
    prev_rows = [
        {"id": 1, "name": "Apple"},
        {"id": 2, "name": "Banana"},
        {"id": 3, "name": "Cherry"},
    ]
    # Row 2 updated, row 3 deleted, row 4 is a new insert
    curr_rows_data = [
        {"id": 1, "name": "Apple"},       # unchanged at index 1
        {"id": 2, "name": "Blueberry"},   # updated at index 2
        # index 3 now gone → will appear in deletes (len(curr) < len(prev))
    ]
    df = pd.DataFrame(curr_rows_data)
    prev = _make_snapshot(prev_rows)
    curr = _make_current_rows(df)
    inserts, updates, deletes = _detect_changes(curr, prev)

    # No new inserts (curr is shorter than prev)
    assert inserts == []
    # Row at index 2 changed name → update
    assert len(updates) == 1
    assert updates[0]["row_dict"]["name"] == "Blueberry"
    # Row at index 3 is missing in current → soft delete
    assert len(deletes) == 1
    assert deletes[0] == 3


def test_change_detection_insert_beyond_previous():
    """New rows appended after the previous snapshot end appear as inserts."""
    prev_rows = [{"id": 1, "name": "Apple"}]
    curr_rows_data = [
        {"id": 1, "name": "Apple"},       # unchanged
        {"id": 2, "name": "Banana"},      # insert
        {"id": 3, "name": "Cherry"},      # insert
    ]
    df = pd.DataFrame(curr_rows_data)
    prev = _make_snapshot(prev_rows)
    curr = _make_current_rows(df)
    inserts, updates, deletes = _detect_changes(curr, prev)

    assert len(inserts) == 2
    names = [r["row_dict"]["name"] for r in inserts]
    assert "Banana" in names
    assert "Cherry" in names
    assert updates == []
    assert deletes == []

