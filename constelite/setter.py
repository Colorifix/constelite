from typing import Generic, TypeVar, Optional, Type, Callable

from functools import wraps

from pydantic import validate_arguments, BaseModel
from pydantic.generics import GenericModel

from constelite import get_method_name, Model, Config, get_config

from loguru import logger


class SetterAPIModel(BaseModel):
    name: Optional[str]
    set_model: Type[Model]
    config: Type[Config]
    fn: Callable


class setter:
    """Wrapper for setters
    """
    __setters = {}

    @classmethod
    def setters(cls):
        return cls.__setters

    def __init__(self, name: str = None):
        self.name = name

    @logger.catch(reraise=True)
    def __call__(self, fn):
        fn_name = fn.__name__

        if fn_name in self.__setters:
            logger.warn(f"Duplicate of {fn_name} found. Skipping...")
            return fn
        else:
            vfn = validate_arguments(fn)

            ret_model = vfn.__annotations__.get('model', None)

            if ret_model is None:
                raise ValueError(
                    f"Getter function {fn_name} has no 'model' argument."
                )

            config_model = vfn.__annotations__.get('config', None)
            if config_model is None:
                raise ValueError(
                    f"Getter function {fn_name} has no 'config' argument or "
                    "'config' type is not specified"
                )

            self.__setters[fn_name] = SetterAPIModel(
                name=self.name,
                set_model=ret_model,
                fn=vfn,
                config=config_model
            )

            @wraps(vfn)
            def wrapper(**kwargs):
                config = kwargs.get('config', None)
                if config is None:
                    kwargs['config'] = get_config(self.config_cls)

                return vfn(**kwargs)

            return wrapper
