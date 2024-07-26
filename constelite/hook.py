from typing import Optional, Callable, Type

import inspect
import re

from pydantic.v1 import BaseModel

from constelite.loggers import Logger

class HookConfig(BaseModel):
    pass

class HookModel(BaseModel):
    path: Optional[str]
    name: Optional[str]
    fn: Callable
    fn_model: Type
    ret_model: Optional[Type]
    slug: str

class Hook(BaseModel):
    @classmethod
    def get_slug(cls):
        pattern = re.compile(r'(?<!^)(?=[A-Z])')
        name = pattern.sub('_', cls.__name__).lower()
        return name

    @classmethod
    def get_model(cls):
        ret_model = cls.run.__annotations__.get('return', None)

        async def wrapper(api, hook_config:HookConfig, logger: Optional[Logger] = None, **kwargs):
            hook = cls(**kwargs)

            run_kwargs = {"api": api}

            if "logger" in inspect.signature(hook.run).parameters:
                run_kwargs['logger'] = logger

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