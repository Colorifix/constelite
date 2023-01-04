from typing import Optional, List
from pydantic import BaseModel, UUID4

from constelite.store import BaseStore


class ConsteliteAPI:
    """Base class for API implementations
    """
    def __init__(
        self,
        name: str,
        version: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        stores: Optional[List[BaseStore]] = []
    ):
        self.name = name
        self.version = version
        self.host = host
        self.port = port
        self.stores = stores

    def run(self):
        pass

    def get_store(self, uid: UUID4):
        return next(
            (
                store for store in self.stores
                if store.uid == uid
            ),
            None
        )
