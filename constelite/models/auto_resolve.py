from typing import Optional, Type
from pydantic.v1 import BaseModel, root_validator, Extra

class AutoResolveBaseModel(BaseModel, extra=Extra.allow):
    model_name: Optional[str] = None

    @root_validator()
    def assign_model(cls, values):
        model_name = values.get('model_name', None)

        values['model_name'] = model_name or cls.__name__
        return values

class FlexibleModel(BaseModel, extra=Extra.allow):
    """Flexibe model.

    A fallback model for when model class cannot be resolved.
    """
    def asmodel(self, model: Type):
        return model(**self.__dict__)
