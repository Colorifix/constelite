import asyncio
import re
from typing import Type, Literal, Union
from typing import get_origin, get_args
from typing_extensions import Annotated


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
                tg.create_task(fn(item))
            )
    
    return [task.result() for task in tasks]