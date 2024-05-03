from python_notion_api import ParagraphBlock, NotionPage
from constelite.store import NotionStore
from constelite.models import StoreModel

from typing import Literal, Optional, Union, Any
from datetime import datetime
from .base_logger import Logger


class NotionLogger(Logger):
    """
    Records the logs on a Notion page as well as writing to loguru.logger.

    When created from the client side, we will not have access to the
    NotionAPI through the NotionStore. The notion_store object can be passed
    as a StoreModel, and the conversion to a NotionStore object will be done
    using the StarliteAPI during protocol validation -> resolve_logger
    -> NotionLogger.from_dict
    """
    notion_page_id: str
    notion_store: Union[NotionStore, StoreModel]
    notion_page: Optional[NotionPage]

    def __init__(self, api:"ConsteliteAPI", notion_store: StoreModel, notion_page_id: str):
        super().__init__(api)
        self._notion_store = notion_store
        self.notion_page_id = notion_page_id
        self.notion_page = None

    async def initialise(self):
        self._notion_store = self.api.get_store(self._notion_store.uid)

        self.notion_page = await self._notion_store.api.get_page(
            self.notion_page_id
        )

    async def log(self, message: Any,
            level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'):
        """
        Log the message through loguru and add to a Notion page too.
        Args:
            message:
            level:

        Returns:

        """
        if self.notion_page is None:
            raise ValueError("Notion page is not assigned. Did you forget to call initialise()?")

        await super().log(message, level)
        # Add time and level to the message
        t = datetime.now().ctime()
        message = f"{t} | {level} | {message}"
        new_block = ParagraphBlock.from_str(message)
        await self.notion_page.add_blocks(blocks=[new_block])
