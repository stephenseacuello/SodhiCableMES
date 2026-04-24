"""
SodhiCable MES — Input Validation Helpers
Reusable validation for POST endpoints.
"""


def validate_required(data, fields):
    """Return list of field names that are missing or empty in *data*."""
    return [f for f in fields if not data.get(f)]


def validate_exists(db, table, pk_col, pk_val):
    """Return True if a row with *pk_val* exists in *table*.*pk_col*."""
    row = db.execute(f"SELECT 1 FROM {table} WHERE {pk_col} = ?", (pk_val,)).fetchone()
    return row is not None


def validate_positive_number(value, field_name="value"):
    """Return an error string if *value* is not a positive number, else None."""
    if not isinstance(value, (int, float)) or value <= 0:
        return f"{field_name} must be a positive number"
    return None
