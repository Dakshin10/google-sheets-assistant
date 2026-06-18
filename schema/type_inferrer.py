import pandas as pd
from datetime import datetime


def infer_sql_type(series):
    """Infers the SQLite data type for a given pandas Series."""
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"

    if pd.api.types.is_float_dtype(series):
        return "REAL"

    # Sample non-null values to check for Date format
    sample_values = [
        str(v)
        for v in series.dropna().head(20)
    ]

    for value in sample_values:
        try:
            datetime.strptime(
                value,
                "%Y-%m-%d"
            )
            return "DATE"
        except ValueError:
            pass

    return "TEXT"
