def discover_worksheets(spreadsheet):
    """Returns a list of dictionaries with metadata for all worksheets in the spreadsheet."""
    worksheets = []
    for ws in spreadsheet.worksheets():
        worksheets.append({
            "title": ws.title,
            "rows": ws.row_count,
            "columns": ws.col_count
        })
    return worksheets
