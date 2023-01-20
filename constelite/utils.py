import re
from typing import Type, Literal


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
