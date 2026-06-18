class LLMException(Exception):
    """Base exception for all Text-to-SQL pipeline errors."""
    pass


class LLMOutputError(LLMException):
    """Raised when the LLM output violates Pydantic or validation rules."""
    pass


class ApprovalError(LLMException):
    """Raised when approval steps fail or queries are rejected."""
    pass
