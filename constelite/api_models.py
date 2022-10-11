from typing import Callable, Optional, Type
from pydantic import BaseModel

from constelite import Model, Config


class APIModel(BaseModel):
    """Base class for API methods
    """
    path: str
    name: Optional[str]
    fn: Callable
    fn_model: Type[BaseModel]
    ret_model: Optional[Type[BaseModel]] = None


class GetterAPIModel(APIModel):
    config: Optional[Type[Config]]


class SetterAPIModel(APIModel):
    set_model: Type[Model]
    config: Optional[Type[Config]]


class ProtocolAPIModel(APIModel):
    pass
