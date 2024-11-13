from typing import Optional, Callable, Type, Any, AsyncGenerator, TYPE_CHECKING, get_args

if TYPE_CHECKING:
    from constelite.api import ConsteliteAPI

import abc

import hashlib
import json

import re

from pydantic.v1 import BaseModel

from constelite.loggers import Logger

class HookConfig(BaseModel):
    pass

class HookModel(BaseModel):
    name: Optional[str]
    fn: Callable
    fn_model: Type
    ret_model: Optional[Type]
    slug: str

class HookCall(BaseModel):
    """A model representing a single call to a hook.

    Attributes:
        hash: A unique hash for this call. Never use this directly, use get_hash instead.
    """
    hash: str | None = None
    model_slug: str
    kwargs: dict
    hook_config: dict | BaseModel
    logger_config: dict | BaseModel |  None = None
    
    def get_hash(self) -> str:
        """Generate a unique hash for this call.
        """
        if self.hash is not None:
            return self.hash
        else:
            data = self.dict()
            data.pop('hash')
            data_md5 = hashlib.md5(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
            self.hash = data_md5
            return data_md5

class Hook(BaseModel):
    @classmethod
    def get_slug(cls):
        pattern = re.compile(r'(?<!^)(?=[A-Z])')
        name = pattern.sub('_', cls.__name__).lower()
        return name

    async def run(self, api: 'ConsteliteAPI', logger: Logger) -> AsyncGenerator[Any, None]:
        yield None

    @classmethod
    def get_model(cls) -> HookModel:
        ret_type = cls.run.__annotations__.get('return', None)
        if not hasattr(ret_type, '__origin__') or not issubclass(ret_type.__origin__, AsyncGenerator):
            raise ValueError(f"Hook {cls.__name__} should return an AsyncGenerator")
        
        ret_model = get_args(ret_type)[0]

        async def wrapper(api, hook_config:HookConfig, logger: Optional[Logger] = None, **kwargs):
            hook = cls(**kwargs)

            run_kwargs = {"api": api, "logger": logger}

            async for ret in hook.run(**run_kwargs):
                await api.trigger_hook(ret=ret, hook_config=hook_config)

        slug = cls.get_slug()

        wrapper.__name__ = slug
        wrapper.__module__ = cls.__module__
        wrapper.__doc__ = cls.__doc__

        return HookModel(
            name=cls.__name__,
            fn=wrapper,
            slug=cls.get_slug(),
            ret_model=ret_model,
            fn_model=cls
        )

class HookManager(abc.ABC):
    @abc.abstractmethod
    def save_hook_call(self, hook_call: HookCall) -> None:
        """
        Save a hook call to the storage.

        This method is intended to be implemented by subclasses to persist the hook call data.

        Args:
            hook_call: The hook call object to be saved. This object contains information about the hook, its configuration, and the parameters passed to it.
        """
        raise NotImplementedError("Subclasses must implement the persist_hook_call method")

    @abc.abstractmethod
    def clear_hook_call(self, hook_call_hash: str) -> None:
        """
        Deletes a hook from the storage.

        This method is intended to be implemented by subclasses to persist the hook call data.

        Args:
            hook_call: The hook call object to be saved. This object contains information about the hook, its configuration, and the parameters passed to it.
        """
        raise NotImplementedError("Subclasses must implement the clear_hook_call method")
    
    @abc.abstractmethod
    def get_hook_calls(self) -> list[HookCall]:
        """
        Returns all the hook calls stored in the storage.

        Returns:
            A list of HookCall objects.
        """
        raise NotImplementedError("Subclasses must implement the get_hook_calls method")

    @abc.abstractmethod
    def contains(self, hook_call_hash: str) -> bool:
        """
        Checks if a hook call with the given hash exists in the storage.

        Args:
            hook_call_hash: The hash of the hook call to be checked.

        Returns:
            True if the hook call exists, False otherwise.
         """
        raise NotImplementedError("Subclasses must implement the contains method")