import sqlglot
import sqlglot.expressions as exp
from exceptions.sync_exceptions import SchemaValidationError


def analyze_sql_ast(sql: str, schema: dict) -> tuple[bool, str]:
    """
    Statically analyzes the SQLite query AST against the cached schema dict.
    Returns (is_valid, error_message).
    """
    try:
        expression = sqlglot.parse_one(sql, read="sqlite")
    except Exception as e:
        return False, f"SQL syntax compilation error: {str(e)}"

    # 1. Enforce strict read-only queries. Block modifications
    unsafe_classes = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
        exp.Create, exp.Command
    )
    
    for node in expression.walk():
        if isinstance(node, unsafe_classes):
            return False, f"Forbidden destructive query node detected: {node.__class__.__name__}. Only SELECT queries are permitted."

    # 2. Verify all referred tables and columns against the schema map
    for node in expression.walk():
        # Validate table exists
        if isinstance(node, exp.Table):
            table_name = node.name.lower()
            # If the node is a CTE alias, skip validation
            # Find if this table name is in any WITH statement CTE list
            is_cte = False
            curr = node
            while curr.parent:
                curr = curr.parent
                if isinstance(curr, exp.With):
                    for cte in curr.expressions:
                        if cte.alias.lower() == table_name:
                            is_cte = True
                            break
                if is_cte:
                    break
            
            if not is_cte and table_name not in schema:
                return False, f"Table reference '{node.name}' does not exist in the active database schema."

        # Validate column exists
        if isinstance(node, exp.Column):
            col_name = node.name.lower()
            ref_table = node.text("table").lower()
            
            # Skip wildcards, system variables, or row_number/virtual values
            if col_name in ("*", "", "row_number") or col_name.startswith("_"):
                continue
                
            if ref_table:
                # If table is a CTE alias, skip checking columns
                is_cte = False
                curr = node
                while curr.parent:
                    curr = curr.parent
                    if isinstance(curr, exp.With):
                        for cte in curr.expressions:
                            if cte.alias.lower() == ref_table:
                                is_cte = True
                                break
                    if is_cte:
                        break
                
                if not is_cte:
                    if ref_table not in schema:
                        return False, f"Table prefix '{ref_table}' on column reference '{node.name}' does not exist."
                    if col_name not in schema[ref_table]:
                        return False, f"Column '{node.name}' does not exist in table '{ref_table}'."
            else:
                # Naked column reference - verify it exists in at least one table in schema
                found = False
                # Also check CTE aliases in parent scopes
                is_cte = False
                curr = node
                while curr.parent:
                    curr = curr.parent
                    if isinstance(curr, exp.With):
                        is_cte = True  # If CTEs exist in query, fallback allow to prevent false positives
                        break
                
                if is_cte:
                    found = True
                else:
                    for tbl, cols in schema.items():
                        if col_name in cols:
                            found = True
                            break
                            
                if not found:
                    return False, f"Column reference '{node.name}' does not match any table in active database schema."

    return True, ""
