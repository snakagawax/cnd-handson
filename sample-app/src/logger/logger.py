from enum import Enum
from typing import Any

from pythonjsonlogger import jsonlogger


class LoggerName(Enum):
    """Logger name defined in uvicorn"""

    DEFAULT = "uvicorn.error"
    ACCESS = "uvicorn.access_custom"


class JsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter for logging.

    This class extends the `jsonlogger.JsonFormatter` class
    and provides a custom implementation for formatting log records as JSON.

    Attributes:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["reserved_attrs"] = [
            "color_message",
            *jsonlogger.RESERVED_ATTRS,
        ]
        super().__init__(*args, **kwargs)  # type: ignore
