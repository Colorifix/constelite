from pydantic.v1 import BaseModel, Field
from loguru import logger
from typing import Literal, Optional, Any


class Logger(BaseModel):
    """
    Class for logging progress, warnings and errors during protocols.
    This base class just outputs to loguru logger
    """
    api: Optional[Any]

    def log(self, message: Any,
            level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'):
        """
        Log the message through loguru and add to a Notion page too.
        Args:
            message:
            level:

        Returns:

        """
        logger.log(level, message)


class LoggerConfig(BaseModel):
    logger_name: str
    logger_kwargs: Optional[dict] = Field(default_factory=dict)
