import os
import importlib
import inspect

from typing import Callable, Optional, List, Type, Dict, Any
from pydantic import UUID4, BaseModel

from constelite.models import Ref, StoreModel, StateModel
from constelite.store import BaseStore
from constelite.guid_map import GUIDMap


class ConsteliteAPI:
    """Base class for API implementations.

    Args:
        name: Name of the API.
        version: Version of the API.
        host: A host to listen.
        port: A port to bind to.
        stores: A list of stores that the API will handle.
        temp_store: A store to use for caching return states of the protocols.
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
        stores: Optional[List[BaseStore]] = [],
        temp_store: Optional[BaseStore] = None,
        dependencies: Optional[Dict[str, Any]] = {},
        guid_map: Optional[GUIDMap] = None
    ):
        self.name = name
        self.version = version
        self.stores = stores
        self.protocols = []
        self._dependencies = dependencies

        self.temp_store = None

        if temp_store is not None:
            self.temp_store = temp_store
            self.stores.append(self.temp_store)

        self._guid_map = guid_map
        self._guid_enabled = False

    def enable_guid(self):
        if self._guid_map is not None:
            for store in self.stores:
                store.set_guid_map(self._guid_map)
        else:
            raise ValueError("Enabling guid failed. No guid_map provided")

    def disable_guid(self):
        for store in self.stores:
            store.disable_guid()

    def discover_protocols(self, module_root: str, bind_path: str = "") -> None:
        """Discovers protocols in the given module

        Args:
            module_root: A name of the module to look for protocols
            bind_path: A path where to bind the protocols
        """
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
                    inspect.isclass(member)
                    and issubclass(member, Protocol)
                    and member != Protocol
                )
            )

            self.protocols.extend(
                [cls.get_model() for _, cls in cls_protocols]
            )

        for protocol_model in self.protocols:
            module_path = protocol_model.fn.__module__
            module_path = ".".join(
                [part for part in module_path.split('.')[:-1]]
            )

            module_path = module_path.replace(
                module_root, ''
            ).replace(
                '.', '/'
            ).strip('/')
            protocol_model.path = os.path.join(
                bind_path, module_path, protocol_model.slug
            )

    def run(self) -> None:
        raise NotImplementedError

    def get_store(self, uid: UUID4) -> StoreModel:
        """Looks up a store by its uid
        """
        return next(
            (
                store for store in self.stores
                if store.uid == uid
            ),
            None
        )

    def get_dependency(self, key):
        return self._dependencies.get(key, None)

    def get_state(self, ref: Ref, cache: bool = True) -> StateModel:
        """Retrieves a state of a reference from store

        Args:
            ref: Input reference.
            cache: Assigns retrieved state to the input reference if `True`

        Returns:
            A state of the reference.

        Raises:
            ValueError:
                If reference store is not known
        """
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
    ret_model: Optional[Type]
    slug: str
