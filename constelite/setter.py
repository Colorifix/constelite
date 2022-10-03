from typing import Generic, TypeVar, Optional
from pydantic import validate_arguments
from pydantic.generics import GenericModel

from constelite import get_method_name, Model

ConfigT = TypeVar('ConfigT')


class Setter(GenericModel, Generic[ConfigT]):
    """Base class for setters
    """
    config: Optional[ConfigT]

    def set(self, model: Model):
        method_name = get_method_name(model.__class__, 'set')
        method = getattr(self, method_name, None)

        if method is None:
            raise AttributeError(
                f"Method '{method_name}' is not defined"
                f" for {self.__class__}"
            )
        validate_arguments(method)(model)
