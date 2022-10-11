from inspect import signature, Parameter
from typing import List, Optional, Type

from pydantic import create_model, validate_arguments

from constelite import get_config, GetterAPIModel, Config

from loguru import logger


class getter:
    """Wrapper for getters
    """
    __getters: List[GetterAPIModel] = []

    @classmethod
    @property
    def getters(cls) -> List[GetterAPIModel]:
        return cls.__getters

    def __init__(self, name: str = None):
        self.name = name

    @staticmethod
    def _generate_model(fn, config_model: Type[Config]):
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

        if config_model is not None:
            fields['config'] = (Optional[config_model], None)
        return create_model(fn.__name__, **fields)

    @logger.catch(reraise=True)
    def __call__(self, fn):
        fn_name = fn.__name__

        if fn_name in self.__getters:
            logger.warn(f"Duplicate of {fn_name} found. Skipping...")
            return fn
        else:
            ret_model = fn.__annotations__.get('return', None)
            if ret_model is None:
                raise ValueError(
                    f'Getter function {fn_name} has no return type specified.'
                )

            config_model = fn.__annotations__.get('config', None)

            fn_model = self._generate_model(fn, config_model)

            def wrapper(**kwargs) -> ret_model:
                if config_model is not None:
                    config = kwargs.get('config', None)
                    if config is None:
                        kwargs['config'] = get_config(config_model)

                return validate_arguments(fn)(**kwargs)

            path = fn.__name__
            wrapper.__name__ = path

            self.__getters.append(
                GetterAPIModel(
                    path=path,
                    name=self.name,
                    ret_model=ret_model,
                    fn=wrapper,
                    fn_model=fn_model,
                    config=config_model
                )
            )

            return wrapper
