from pydantic import BaseModel, Extra
from typing import Type


class Model(BaseModel):
    pass


class FlexibleModel(Model, extra=Extra.allow):
    def asmodel(self, model: Type[Model]):
        return model(**self.__dict__)
