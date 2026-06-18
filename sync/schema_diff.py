def diff_schemas(d1_schema: list, new_schema: list) -> dict:
    """
    Compares two schemas and identifies added, removed, renamed, and type-changed columns.
    Both schemas should be lists of dicts: [{'name': 'col_name', 'type': 'col_type'}, ...]
    """
    d1_map = {col["name"].lower(): col for col in d1_schema}
    new_map = {col["name"].lower(): col for col in new_schema}

    added = []
    removed = []
    type_changed = []
    renamed = []

    # Identify added and type_changed
    for col in new_schema:
        name_lower = col["name"].lower()
        if name_lower not in d1_map:
            added.append(col)
        else:
            d1_col = d1_map[name_lower]
            if d1_col["type"].upper() != col["type"].upper():
                type_changed.append({
                    "name": col["name"],
                    "old_type": d1_col["type"],
                    "new_type": col["type"]
                })

    # Identify removed
    for col in d1_schema:
        name_lower = col["name"].lower()
        if name_lower not in new_map:
            removed.append(col)

    # Heuristic for Renamed Columns:
    # If a column was removed and another added with the same type, we infer it as a rename.
    matched_removed = set()
    matched_added = set()
    
    for r_col in removed:
        for a_col in added:
            if r_col["name"].lower() in matched_removed or a_col["name"].lower() in matched_added:
                continue
            # If same type, assume renamed
            if r_col["type"].upper() == a_col["type"].upper():
                renamed.append((r_col["name"], a_col["name"], r_col["type"]))
                matched_removed.add(r_col["name"].lower())
                matched_added.add(a_col["name"].lower())
                break

    # Filter out matched renamed columns from raw added/removed lists
    added = [a for a in added if a["name"].lower() not in matched_added]
    removed = [r for r in removed if r["name"].lower() not in matched_removed]

    return {
        "added": added,
        "removed": removed,
        "renamed": renamed,
        "type_changed": type_changed
    }
