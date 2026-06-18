class SyncException(Exception):
    """Base exception for all sync process failures."""
    pass


class SchemaValidationError(SyncException):
    """Raised when incoming schema cannot be validated or diffed."""
    pass


class MigrationError(SyncException):
    """Raised when generating or running structural migration DDL queries fails."""
    pass


class StagingLoadError(SyncException):
    """Raised when loading data into staging tables fails verification metrics."""
    pass
