from typing import Type, Callable, Optional
from pydantic import validate_arguments, BaseModel

from functools import wraps

from constelite import Model, Config, get_config

from loguru import logger


class GetterAPIModel(BaseModel):
    name: Optional[str]
    ret_model: Type[Model]
    config: Type[Config]
    fn: Callable


class getter:
    """Wrapper for getters
    """
    __getters = {}

    @classmethod
    def getters(cls):
        return cls.__getters

    def __init__(self, name: str = None):
        self.name = name

    @logger.catch(reraise=True)
    def __call__(self, fn):
        fn_name = fn.__name__

        if fn_name in self.__getters:
            logger.warn(f"Duplicate of {fn_name} found. Skipping...")
            return fn
        else:
            vfn = validate_arguments(fn)

            ret_model = vfn.__annotations__.get('return', None)
            if ret_model is None:
                raise ValueError(
                    f'Getter function {fn_name} has no return type specified.'
                )

            config_model = vfn.__annotations__.get('config', None)

            self.__getters[fn_name] = GetterAPIModel(
                name=self.name,
                ret_model=ret_model,
                fn=vfn,
                config=config_model
            )

            @wraps(vfn)
            def wrapper(**kwargs):
                config = kwargs.get('config', None)
                if config is None:
                    kwargs['config'] = get_config(config_model)

                return vfn(**kwargs)

            return wrapper
