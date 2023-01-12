from typing import List, Optional
from inspect import signature, Parameter
import re

from pydantic import BaseModel, validate_arguments, create_model

from constelite.api import ProtocolModel

from loguru import logger

from functools import wraps


class protocol:
    """Decorator for protocols
    """
    __protocols: List[ProtocolModel] = []

    @classmethod
    @property
    def protocols(cls) -> List[ProtocolModel]:
        return cls.__protocols

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

        return create_model(fn.__name__, **fields)

    def __call__(self, fn):
        fn_name = fn.__name__

        if fn_name in self.__protocols:
            logger.warn(f"Duplicate of {fn_name} found. Skipping...")
            return fn
        else:

            ret_model = fn.__annotations__.get('return', None)
            if ret_model is None:
                raise ValueError(
                    f'Getter function {fn_name} has no return type specified.'
                )

            model = self._generate_model(fn)

            # def wrapper(**kwargs) -> ret_model:
            #     to_store = kwargs.pop('store')

            #     ret = validate_arguments(fn)(**kwargs)

            #     if to_store is True:
            #         store = get_store()
            #         return store.store(ret)
            #     else:
            #         return ret

            # path = fn.__name__
            # wrapper.__name__ = path

            # @wraps(
            #     fn,
            #     assigned=[
            #         '__module__',
            #         '__name__',
            #         '__doc__'
            #     ]
            # )
            def wrapper(self, data: model) -> ret_model:
                args = {
                    field_name: getattr(data, field_name, None)
                    for field_name in data.__fields__.keys()
                }
                return fn(**args)

            wrapper.__name__ = fn.__name__
            wrapper.__module__ = fn.__module__
            wrapper.__doc__ = fn.__doc__

            fn._protocol_model = ProtocolModel(
                name=self.name,
                fn=wrapper,
                slug=fn.__name__,
                # ret_model=ret_model,
                fn_model=model,
                # path=path
            )

            # self.__protocols.append(
            #     ProtocolModel(
            #         name=self.name,
            #         fn=wrapper,
            #         ret_model=ret_model,
            #         fn_model=model,
            #         path=path
            #     )
            # )

            return validate_arguments(fn)


class Protocol(BaseModel):
    _name: Optional[str]

    @classmethod
    def get_slug(cls):
        pattern = re.compile(r'(?<!^)(?=[A-Z])')
        name = pattern.sub('_', cls.__name__).lower()
        return name

    @classmethod
    def get_model(cls):
        ret_type_hint = cls.run.__annotations__.get('return', None)

        def wrapper(self, data: cls) -> ret_type_hint:
            return data.run()

        return ProtocolModel(
            name=cls.getattr('_name', None) or cls.__name__,
            fn=wrapper,
            slug=cls.get_slug()
        )
