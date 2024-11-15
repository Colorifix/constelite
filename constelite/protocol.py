import typing
from typing import  Callable, Any, TYPE_CHECKING
import abc
import asyncio
import inspect
import re

from pydantic.v1 import BaseModel, create_model

from constelite.loggers import Logger

if TYPE_CHECKING:
    from constelite.api.api import ConsteliteAPI


class ProtocolModel(BaseModel):
    """Base class for API methods
    """
    path: str | None = None
    name: str | None = None
    fn: Callable
    fn_model: type[BaseModel]
    ret_model: type[Any] | None
    slug: str

class ProtocolProtocol(typing.Protocol):
    def get_model(self) -> ProtocolModel: ...

class CallableProtocol(ProtocolProtocol):
    def __call__(self, api: 'ConsteliteAPI', logger: Logger, **kwargs) -> Any:...

class protocol:
    """Decorator for protocols
    """

    def __init__(self, name):
        self.name = name

    @staticmethod
    def _generate_model(fn):
        RESERVED_KWARGS = ['api', 'logger']
        fields = {}

        for param_name, param in inspect.signature(fn).parameters.items():
            if param_name in RESERVED_KWARGS:
                continue
            if param.annotation == inspect.Parameter.empty:
                raise ValueError(f"Signature of {fn.__name__} is not valid. Parameter '{param_name}' has no annotation.")
            if param.default == inspect.Parameter.empty:
                fields[param_name] = (param.annotation, ...)
            else:
                fields[param_name] = (param.annotation, param.default)

        return create_model(fn.__name__, **fields)

    def wrap_fn(self, fn):
        async def wrapper(api, logger: Logger, **kwargs):
            if inspect.iscoroutinefunction(fn):
                return await fn(api=api, logger=logger, **kwargs)
            else:
                return await asyncio.to_thread(fn, api=api, logger=logger, **kwargs)
        
        wrapper.__name__ = fn.__name__
        wrapper.__module__ = fn.__module__
        wrapper.__doc__ = fn.__doc__

        return wrapper
    def __call__(self, fn) -> CallableProtocol:
        fn_name = fn.__name__

        if 'return' not in fn.__annotations__:
            raise ValueError(
                f'Getter function {fn_name} has no return type specified.'
            )

        ret_model = fn.__annotations__['return']

        model = self._generate_model(fn)

        fn.get_model = lambda: ProtocolModel(
            name=self.name,
            fn=self.wrap_fn(fn),
            slug=fn.__name__,
            ret_model=ret_model,
            fn_model=model,
        )
        

        return fn


class Protocol(BaseModel):
    @classmethod
    def get_slug(cls):
        pattern = re.compile(r'(?<!^)(?=[A-Z])')
        name = pattern.sub('_', cls.__name__).lower()
        return name
    
    @abc.abstractmethod
    async def run(self, api: 'ConsteliteAPI', logger: Logger) -> Any:
        raise NotImplementedError("Subclasses must implement this method")

    @classmethod
    def get_model(cls):
        ret_model = cls.run.__annotations__.get('return', None)

        async def wrapper(api, logger: Logger, **kwargs):
            protocol = cls(**kwargs)
            return await protocol.run(api=api, logger=logger)
            
        slug = cls.get_slug()

        wrapper.__name__ = slug
        wrapper.__module__ = cls.__module__
        wrapper.__doc__ = cls.__doc__

        return ProtocolModel(
            name=cls.__name__,
            fn=wrapper,
            slug=cls.get_slug(),
            ret_model=ret_model,
            fn_model=cls
        )
