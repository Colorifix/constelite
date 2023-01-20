from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, root_validator, Extra

from constelite.utils import all_subclasses


class AutoResolveBaseModel(BaseModel):
    model_name: Optional[str]

    @root_validator()
    def assign_model(cls, values):
        values['model_name'] = cls.__name__
        return values


class FlexibleModel(BaseModel, extra=Extra.allow):
    """Flexibe model.

    A fallback model for when model class cannot be resolved.
    """
    def asmodel(self, model: Type):
        return model(**self.__dict__)
