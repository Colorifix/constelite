import os
import importlib
import inspect
import asyncio

from uuid import uuid4, UUID

from typing import Callable, Optional, List, Type, Dict, Any, Union
from pydantic.v1 import UUID4, BaseModel

from tinydb import TinyDB, Query

from constelite.models import Ref, StoreModel, StateModel
from constelite.store import BaseStore, AsyncBaseStore
from constelite.guid_map import GUIDMap, AsyncGUIDMap
from constelite.loggers.base_logger import LoggerConfig, Logger
from constelite.protocol import Protocol, ProtocolModel
from constelite.hook import HookModel, HookConfig, HookManager, HookCall
from loguru import logger

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

    def __init__(
        self,
        name: str,
        version: Optional[str] = None,
        stores: Optional[List[BaseStore]] = [],
        temp_store: Optional[BaseStore] = None,
        dependencies: Optional[Dict[str, Any]] = {},
        guid_map: Optional[GUIDMap] = None,
        async_guid_map: Optional[AsyncGUIDMap] = None,
        loggers: Optional[List[Type[Logger]]] = None,
        hook_manager: Optional[HookManager] = None,
    ):
        self.name = name
        self.version = version
        self.stores = stores or []
        self.protocols: List[ProtocolModel] = []
        self.hooks: List[HookModel] = []
        self._dependencies = dependencies

        self.hook_manager = hook_manager
        self.hook_tasks: dict[str, asyncio.Task] = {}
        self.temp_store = None

        if temp_store is not None:
            self.temp_store = temp_store
            self.stores.append(self.temp_store)

        self._guid_map = guid_map
        self._async_guid_map = async_guid_map
        self._guid_enabled = False

        self.loggers = loggers

    def enable_guid(self):
        if self._guid_map is not None:
            for store in self.stores:
                if isinstance(store, BaseStore):
                    store.set_guid_map(self._guid_map)
                elif isinstance(store, AsyncBaseStore):
                    store.set_guid_map(self._async_guid_map)
                else:
                    raise ValueError(
                        "Enabling guid failed. Store {store} is not BaseStore or AsyncBaseStore"
                    )
        else:
            raise ValueError("Enabling guid failed. No guid_map provided")

    def disable_guid(self):
        for store in self.stores:
            store.disable_guid()

    async def get_logger(self,
                   logger_config: Optional[Union[LoggerConfig, dict]]
                   ) -> Logger:
        """
        Creates a logger instance. Gets the logger class by matching the name
        in the logger_config to the logger class name.
        The default logger is just outputting to loguru.logger
        Args:
            logger_config: LoggerConfig instance or the equivalent dictionary.

        Returns:

        """
        if logger_config is None:
            logger_cls = Logger  # Default option. Needs no kwargs.
            logger_kwargs = {}
        else:
            if isinstance(logger_config, LoggerConfig):
                logger_config = logger_config.dict()
            logger_cls = next(
                (l for l in self.loggers if l.__name__ ==
                 logger_config['logger_name']),
                None
            )
            if logger_cls is None:
                raise ValueError(
                    f"Don't recognise the logger cls with name"
                    f" {logger_config['logger_name']}"
                )
            logger_kwargs = logger_config['logger_kwargs']

        logger = logger_cls(api=self, **logger_kwargs)
        await logger.initialise()

        return logger
    def add_protocol(self, protocol: Union[Type[Protocol], Callable]):
        if issubclass(protocol, Protocol):
            protocol_model = protocol.get_model()
        else:
            protocol_model = getattr(protocol, '_protocol_model', None)

        if protocol_model is not None:
            protocol_model.path = protocol_model.name
            self.protocols.append(protocol_model)
        else:
            logger.warning("Supplied protocol is invalid")

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
    
    def discover_hooks(self, module_root: str, bind_path: str = "") -> None:
        module = importlib.import_module(module_root)

        if module is not None:
            from constelite.hook import Hook

            hooks = inspect.getmembers(
                module,
                lambda member: (
                    inspect.isclass(member)
                    and issubclass(member, Hook)
                    and member != Hook
                )
            )

            self.hooks.extend(
                [cls.get_model() for _, cls in hooks]
            )

    def run(self) -> None:
        raise NotImplementedError

    def get_hook(self, slug: str) -> HookModel | None:
        hook = next(
            (h for h in self.hooks if h.slug == slug),
            None
        )

        return hook

    async def start_persistent_hooks(self):
        if self.hook_manager is not None:
            for hook_call in self.hook_manager.get_hook_calls():
                logger.info(f"Starting persistent hook: {hook_call.model_slug} ({hook_call.get_hash()})")
                try:
                    await self.start_hook(
                        slug=hook_call.model_slug,
                        hook_config=hook_call.hook_config,
                        logger_config=hook_call.logger_config,
                        **hook_call.kwargs
                    )
                    # self.hook_manager.clear_hook_call(hook_call.uuid)
                except Exception as e:
                    logger.error(f"Failed to start hook: {repr(e)}")
                
    def hook_task_done_callback(self, hook_call_hash: str):
        def wrapper(future):
            if future.cancelled():
                logger.info(f"Hook task {hook_call_hash} was cancelled")
            else:
                logger.info(f"Hook task {hook_call_hash} completed")
            if self.hook_manager is not None:
                self.hook_manager.clear_hook_call(hook_call_hash)
            self.hook_tasks.pop(hook_call_hash, None)
        return wrapper

    async def start_hook(self, slug:str, hook_config: HookConfig, **kwargs) -> str:
        hook = self.get_hook(slug=slug)
        
        logger_config = kwargs.pop("logger_config", None)

        hook_logger = await self.get_logger(logger_config)
        
        if hook is None:
            raise ValueError(f"Unknown hook with slug {slug}")
        else:
            hook_call = HookCall(model_slug=slug, kwargs=kwargs, hook_config=hook_config, logger_config=logger_config)
            hook_call_hash = hook_call.get_hash()

            if hook_call_hash not in self.hook_tasks:
                hook_task =  asyncio.create_task(hook.fn(api=self, hook_config=hook_config, logger=hook_logger, **kwargs))
            else:
                logger.info(f"Hook call already in progress: {hook_call.hash}")
                return hook_call_hash
            
            self.hook_tasks[hook_call_hash] = hook_task
            
            if self.hook_manager is not None:
                try:
                    if not self.hook_manager.contains(hook_call_hash):
                        self.hook_manager.save_hook_call(hook_call)
                    else:
                        logger.info(f"Hook call already persisted: {hook_call_hash})")
                except Exception as e:
                    logger.error(f"Failed to persist hook call: {repr(e)}")
            
            hook_task.add_done_callback(
                self.hook_task_done_callback(hook_call_hash)
            )
            
            return hook_call_hash

    def cancel_hook(self, hook_call_hash: str):
        hook_task = self.hook_tasks.get(hook_call_hash, None)
        if hook_task is not None:
            hook_task.cancel()

    async def trigger_hook(self, ret: Any, hook_config: HookConfig) -> None:
        raise NotImplementedError
    
    def get_store(self, uid: UUID4) -> StoreModel | None:
        """Looks up a store by its uid
        """
        return next(
            (
                store for store in self.stores
                if store.uid == uid
            ),
            None
        )

    def get_protocol(self, slug: str) -> ProtocolModel | None:
        protocol = next(
            (p for p in self.protocols if p.slug == slug),
            None
        )

        return protocol

    async def run_protocol(self, slug: str, **kwargs):
        protocol = self.get_protocol(slug=slug)

        if protocol is None:
            raise ValueError(f"Unknown protocol with slug {slug}")
        else:
            return await protocol.fn(api=self, **kwargs)

    def get_dependency(self, key):
        return self._dependencies.get(key, None)

    async def get_state(self, ref: Ref, cache: bool = True, refresh=True) -> StateModel:
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
        if ref.state is not None and not refresh:
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

                state = (await store.get(ref)).state
                if cache is True:
                    ref.state = state

        return state


class ProtocolModel(BaseModel):
    """Base class for API methods
    """
    path: Optional[str] = None
    name: Optional[str] = None
    fn: Callable
    fn_model: Type
    ret_model: Optional[Type] = None
    slug: str
