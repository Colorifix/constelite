import re
from typing import Type, Literal


def get_method_name(cls: Type, method_type: Literal['get', 'set']):
    pattern = re.compile(r'(?<!^)(?=[A-Z])')
    name = pattern.sub('_', cls.__name__).lower()
    return f"{method_type}_{name}"
