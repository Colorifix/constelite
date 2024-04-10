from typing import Any, Optional
from inspect import signature, Parameter
import re

from pydantic.v1 import BaseModel, validate_arguments, create_model

from constelite.api import ProtocolModel


class protocol:
    """Decorator for protocols
    """

    def __init__(self, name):
        self.name = name

    @staticmethod
    def _generate_model(fn):
        fields = {
            param_name:
            (
                param.annotation,
                ...
            )
            if param.default == Parameter.empty
            else (
                param.annotation,
                param.default
            )
            for param_name, param in signature(fn)._parameters.items()
        }

        fields.pop('api')

        return create_model(fn.__name__, **fields)

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
            fn=validate_arguments(fn),
            slug=fn.__name__,
            ret_model=ret_model,
            fn_model=model,
        )

        return validate_arguments(fn)


class Protocol(BaseModel):
    _name: Optional[str]
    api: Optional[Any]

    @classmethod
    def get_slug(cls):
        pattern = re.compile(r'(?<!^)(?=[A-Z])')
        name = pattern.sub('_', cls.__name__).lower()
        return name

    @classmethod
    def get_model(cls):
        ret_model = cls.run.__annotations__.get('return', None)

        def wrapper(api, **kwargs) -> ret_model:
            protocol = cls(**kwargs)
            return protocol.run(api)

        slug = cls.get_slug()

        wrapper.__name__ = slug
        wrapper.__module__ = cls.__module__
        wrapper.__doc__ = cls.__doc__

        return ProtocolModel(
            name=getattr(cls, '_name', None) or cls.__name__,
            fn=wrapper,
            slug=cls.get_slug(),
            ret_model=ret_model,
            fn_model=cls
        )
