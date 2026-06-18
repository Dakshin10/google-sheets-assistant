import uuid
from contextlib import contextmanager
from monitoring.logger import correlation_id_var, request_id_var


@contextmanager
def trace_request(request_id=None):
    """Sets a unique request ID for the lifespan of a transaction."""
    token = request_id_var.set(request_id or str(uuid.uuid4()))
    try:
        yield request_id_var.get()
    finally:
        request_id_var.reset(token)


@contextmanager
def trace_correlation(correlation_id=None):
    """Sets a unique correlation ID to associate related requests together."""
    token = correlation_id_var.set(correlation_id or str(uuid.uuid4()))
    try:
        yield correlation_id_var.get()
    finally:
        correlation_id_var.reset(token)
