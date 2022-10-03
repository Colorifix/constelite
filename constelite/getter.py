from typing import List, Generic, Optional, TypeVar
from pydantic import validate_arguments
from pydantic.generics import GenericModel
from constelite import get_method_name, Model


class getter:
    """Wrapper for getters
    """
    __getters = {}

    @classmethod
    def getters(cls):
        return cls.__getters

    def __init__(self, models: List[Model]):
        self.models = models

    def __call__(self, cls):
        for model in self.models:
            if model not in self.__getters:
                self.__getters[model] = []
            self.__getters[model].append(cls)


ConfigT = TypeVar('ConfigT')


class Getter(GenericModel, Generic[ConfigT]):
    """Getter base class
    """
    config: Optional[ConfigT]

    def get(self, cls, **kwargs):
        method_name = get_method_name(cls, 'get')

        method = getattr(self, method_name, None)

        if method is None:
            raise AttributeError(
                f"Method '{method_name}' is not defined"
                f" for {cls}"
            )

        return validate_arguments(method)(**kwargs)
