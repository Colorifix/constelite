from types import FunctionType
import functools

from typing import TypeVar, Awaitable
from functools import wraps
import asyncio
import datetime
import re

import pkgutil
import importlib
import inspect

from types import ModuleType
from typing import Type, Literal, Union,  Callable, Any
from typing import get_origin, get_args
from typing_extensions import Annotated
from loguru import logger


def resolve_forward_ref(forward_ref, root_cls):
    return next(
        (
            cls for cls in all_subclasses(root_cls)
            if cls.__name__ == forward_ref.__forward_arg__
        ),
        None
    )


def get_method_name(cls: Type, method_type: Literal['get', 'set']):
    pattern = re.compile(r'(?<!^)(?=[A-Z])')
    name = pattern.sub('_', cls.__name__).lower()
    return f"{method_type}_{name}"


def all_subclasses(cls):
    for sub_cls in cls.__subclasses__():
        yield sub_cls
        for sub_sub_cls in all_subclasses(sub_cls):
            yield sub_sub_cls


def is_optional(field):
    return get_origin(field) is Union and \
           type(None) in get_args(field)


def is_annotated(field):
    return get_origin(field) is Annotated


def to_thread(fn):
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    
    wrapper._sync_fn = fn

    return wrapper

async def async_map(fn, iterable):
    tasks = []
    async with asyncio.TaskGroup() as tg:
        for item in iterable:
            tasks.append(
                tg.create_task(async_log_exception(fn)(item))
            )

    return [task.result() for task in tasks]


def get_field_extra(field, key_name):
    """
    Get a value from a Pydantic field json schema extra dict
    Args:
        field:
        key_name:

    Returns:

    """
    extra_info = field.field_info.extra
    key_value = None
    if 'json_schema_extra' in extra_info:
        key_value = extra_info[
            'json_schema_extra'
        ].get(key_name, None)
    return key_value


class EntryDeletedException(Exception):
    pass


def get_exception_string(err: Union[Exception, ExceptionGroup]) -> str:
    """
    Helps get the error message from a task group
    Args:
        err:

    Returns:

    """
    if isinstance(err, ExceptionGroup):
        return repr([get_exception_string(e) for e in err.exceptions])
    return repr(err)

def log_exception(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapped_fn(*args, **kwargs):
        try:
            ret = fn(*args, **kwargs)
            return ret
        except Exception as e:
            logger.patch(lambda r: r.update(function=fn.__name__, name= fn.__module__, line=-1)).error(repr(e))
            raise e
    return wrapped_fn

C = TypeVar('C', bound=Callable)

def async_log_exception(fn: C) -> C:
    @wraps(fn)
    async def wrapped_fn(*args, **kwargs):
        try:
            ret = await fn(*args, **kwargs)
            return ret
        except Exception as e:
            
            fn_name = getattr(fn, '__name__', fn.__repr__)
            fn_module = getattr(fn, '__module__', 'unnknown_module')
            
            if isinstance(fn, FunctionType):
                fn_name = fn.__name__
            elif isinstance(fn, functools.partial):
                fn_name = fn.func.__name__
                fn_module = fn.func.__module__

            logger.patch(lambda r: r.update(function=fn_name, name= fn_module, line=-1)).error(repr(e))
            raise e
    return wrapped_fn

def discover_members(root_module: ModuleType, predicate: Callable[[Any], bool]) -> list[Any]:
    members = []
    for _, module_name, is_pkg in pkgutil.walk_packages(root_module.__path__, root_module.__name__ + "."):
        if not is_pkg:
            try:
                module = importlib.import_module(module_name)
                new_members = inspect.getmembers(
                    module,
                    predicate
                )
                members.extend([member for _, member in new_members])
            except ImportError:
                logger.error(f"Failed to import module: {module_name}")
    return members