import os
import importlib
import inspect

from typing import Callable, Optional, List
from pydantic import UUID4, BaseModel

from constelite.store import BaseStore


class ConsteliteAPI:
    """Base class for API implementations
    """
    __instance = None

    def __new__(cls, *args, **kwargs):
        new = super().__new__(cls)
        if ConsteliteAPI.__instance is None:
            ConsteliteAPI.__instance = new
        return new

    @classmethod
    @property
    def api(cls):
        return cls.__instance

    def __init__(
        self,
        name: str,
        version: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        stores: Optional[List[BaseStore]] = [],
    ):
        self.name = name
        self.version = version
        self.host = host
        self.port = port
        self.stores = stores
        self.protocols = []

    def discover_protocols(self, module_root: str, bind_path: str):
        module = importlib.import_module(module_root)
        if module is not None:
            fn_protocols = inspect.getmembers(
                module,
                lambda member: (
                    callable(member)
                    and hasattr(member, '_protocol_model')
                )
            )

            self.protocols.extend(
                [fn._protocol_model for _, fn in fn_protocols]
            )

            from constelite.protocol import Protocol

            cls_protocols = inspect.getmembers(
                module,
                lambda member: (
                    inspect.isclass(member) and issubclass(member, Protocol)
                )
            )

            self.protocols.extend(
                [cls.get_model() for cls in cls_protocols]
            )

        for protocol_model in self.protocols:
            module_path = protocol_model.fn.__module__.replace(
                module_root, ''
            ).replace(
                '.', '/'
            ).strip('/')
            protocol_model.path = os.path.join(
                bind_path, module_path, protocol_model.slug
            )

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


class ProtocolModel(BaseModel):
    """Base class for API methods
    """
    path: Optional[str]
    name: Optional[str]
    fn: Callable
    slug: str
