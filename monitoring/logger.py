import logging
import json
import time
import sys
from contextvars import ContextVar

# Context variables for correlation and request tracing
correlation_id_var = ContextVar("correlation_id", default="SYSTEM")
request_id_var = ContextVar("request_id", default="SYSTEM")


class StructuredJSONFormatter(logging.Formatter):
    """Formats logs into structured JSON objects."""
    def format(self, record):
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "correlation_id": correlation_id_var.get(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logger(name="sheets_d1_agent"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = StructuredJSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger


logger = setup_logger()
