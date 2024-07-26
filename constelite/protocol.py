from typing import Optional, Type, Callable, Any
import asyncio
import inspect
import re

from pydantic.v1 import BaseModel, validate_arguments, create_model

from constelite.loggers import Logger, LoggerConfig

class ProtocolModel(BaseModel):
    """Base class for API methods
    """
    path: Optional[str]
    name: Optional[str]
    fn: Callable
    fn_model: Type
    ret_model: Optional[Type]
    slug: str


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
        async def wrapper(api, logger: Optional[Logger] = None, **kwargs):
            kwargs['api'] = api

            if "logger" in inspect.signature(fn).parameters:
                kwargs['logger'] = logger
            
            if inspect.iscoroutinefunction(fn):
                return await fn(**kwargs)
            else:
                return await asyncio.to_thread(fn, **kwargs)
        
        wrapper.__name__ = fn.__name__
        wrapper.__module__ = fn.__module__
        wrapper.__doc__ = fn.__doc__

        return wrapper
    def __call__(self, fn):
        fn_name = fn.__name__

        if 'return' not in fn.__annotations__:
            raise ValueError(
                f'Getter function {fn_name} has no return type specified.'
            )

        ret_model = fn.__annotations__['return']

        model = self._generate_model(fn)

        fn._protocol_model = ProtocolModel(
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

    @classmethod
    def get_model(cls):
        ret_model = cls.run.__annotations__.get('return', None)

        async def wrapper(api, logger: Optional[Logger] = None, **kwargs):
            protocol = cls(**kwargs)

            run_kwargs = {"api": api}

            if "logger" in inspect.signature(protocol.run).parameters:
                run_kwargs['logger'] = logger

            if inspect.iscoroutinefunction(protocol.run):
                return await protocol.run(**run_kwargs)
            else:
                return await asyncio.to_thread(protocol.run, **run_kwargs)

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
