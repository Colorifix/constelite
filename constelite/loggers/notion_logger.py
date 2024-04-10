from python_notion_api import ParagraphBlock, NotionPage
from constelite.store import NotionStore
from constelite.models import StoreModel
from pydantic.v1 import validator
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

    class Config:
        arbitrary_types_allowed = True

    @validator('notion_page', always=True)
    def get_log_page(cls, v, values):
        """
        Use the NotionStore.NotionAPI to get the NotionPage on which to record
        the log.
        If the notion_store is not a NotionStore object, it will be a
        StoreModel. Can be converted to a NotionStore object using the API
        in the from_dict function.
        Args:
            v:
            values:

        Returns:

        """
        notion_store = values.get('notion_store')
        if not isinstance(values['notion_store'], NotionStore):
            # the notion store is a StoreModel.
            # Need to get the actual notion store
            notion_store = values['api'].get_store(notion_store.uid)

        notion_page = notion_store.api.get_page(
            values['notion_page_id']
        )
        return notion_page

    def log(self, message: Any,
            level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'):
        """
        Log the message through loguru and add to a Notion page too.
        Args:
            message:
            level:

        Returns:

        """
        super().log(message, level)
        # Add time and level to the message
        t = datetime.now().ctime()
        message = f"{t} | {level} | {message}"
        new_block = ParagraphBlock.from_str(message)
        self.notion_page.add_blocks(blocks=[new_block])
