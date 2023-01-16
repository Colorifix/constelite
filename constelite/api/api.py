import os
import importlib
import inspect

from typing import Callable, Optional, List, Type
from pydantic import UUID4, BaseModel

from constelite.models import Ref
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
        temp_store: Optional[BaseStore] = None
    ):
        self.name = name
        self.version = version
        self.host = host
        self.port = port
        self.stores = stores
        self.protocols = []

        if temp_store is not None:
            self.temp_store = temp_store
            self.stores.append(self.temp_store)

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

    def get_state(self, ref: Ref, cache: bool = True):
        if ref.state is not None:
            state = ref.state
        else:
            if ref.record is not None:

                store = next(
                    (
                        store for store in self.stores
                        if store.uid == ref.record.store.uid
                    ),
                    None
                )

                if store is None:
                    raise ValueError(
                        "Environment api does not have"
                        f"a {ref.record.store.name} store("
                        f"{ref.record.store.uid})"
                    )

                state = store.get(ref).state
                if cache is True:
                    ref.state = state

        return state


class ProtocolModel(BaseModel):
    """Base class for API methods
    """
    path: Optional[str]
    name: Optional[str]
    fn: Callable
    fn_model: Type
    ret_model: Type
    slug: str
