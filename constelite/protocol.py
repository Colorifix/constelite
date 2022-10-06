from typing import Dict, Callable
from pydantic import validate_arguments, BaseModel

from constelite import Model

from loguru import logger


class ProtocolAPIModel(BaseModel):
    name: str
    fn: Callable[..., Dict[str, Model]]


class protocol:
    """Decorator for protocols
    """
    __protocols = {}

    @property
    @classmethod
    def protocols(cls):
        return cls.__protocols

    def __init__(self, name):
        self.name = name

    def __call__(self, fn):
        fn_name = fn.__name__

        if fn_name in self.__protocols:
            logger.warn(f"Duplicate of {fn_name} found. Skipping...")
            return fn
        else:
            vfn = validate_arguments(fn)
            self.__protocols[fn_name] = ProtocolAPIModel(
                name=self.name,
                fn=vfn
            )

            return vfn
