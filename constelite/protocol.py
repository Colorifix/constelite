from typing import List, Optional

from inspect import signature, Parameter

from pydantic import validate_arguments, create_model

from constelite import ProtocolAPIModel, get_store

from loguru import logger


class protocol:
    """Decorator for protocols
    """
    __protocols: List[ProtocolAPIModel] = []

    @classmethod
    @property
    def protocols(cls) -> List[ProtocolAPIModel]:
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

        fields['store'] = (Optional[bool], False)

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

            def wrapper(**kwargs) -> ret_model:
                to_store = kwargs.pop('store')

                ret = validate_arguments(fn)(**kwargs)

                if to_store is True:
                    store = get_store()
                    return store.store(ret)
                else:
                    return ret

            path = fn.__name__
            wrapper.__name__ = path

            self.__protocols.append(
                ProtocolAPIModel(
                    name=self.name,
                    fn=wrapper,
                    ret_model=ret_model,
                    fn_model=model,
                    path=path
                )
            )

            return validate_arguments(fn)
