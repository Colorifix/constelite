from pydantic.v1 import BaseModel, Field
from loguru import logger
from typing import Literal, Optional, Any

class Logger:
    """
    Class for logging progress, warnings and errors during protocols.
    This base class just outputs to loguru logger
    """
    api: Optional[Any]

    def __init__(self, api: "ConsteliteAPI"):
        self.api = api

    async def initialise(self):
        pass

    async def log(self, message: Any,
            level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'):
        """
        Log the message through loguru and add to a Notion page too.
        Args:
            message:
            level:

        Returns:

        """
        logger.log(level, message)

    async def error(self, message: Any):
        await self.log(message, level='ERROR')

class LoggerConfig(BaseModel):
    logger_name: str
    logger_kwargs: Optional[dict] = Field(default_factory=dict)
