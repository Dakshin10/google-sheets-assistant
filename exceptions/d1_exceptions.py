class D1Exception(Exception):
    """Base exception for all D1 operations."""
    pass


class D1ConnectionError(D1Exception):
    """Raised when connecting to Cloudflare D1 REST endpoint fails."""
    pass


class D1QueryExecutionError(D1Exception):
    """Raised when D1 REST API executes a query but returns an API level error."""
    def __init__(self, message, sql=None, error_code=None):
        super().__init__(message)
        self.sql = sql
        self.error_code = error_code
