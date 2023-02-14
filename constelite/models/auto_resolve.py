from typing import Optional, Type
from pydantic import BaseModel, root_validator, Extra

from pydantic.main import ModelMetaclass

from constelite.utils import is_optional, is_annotated


class AutoResolveMeta(ModelMetaclass):
    def __new__(cls, name, bases, namespaces, **kwargs):
        annotations = namespaces.get('__annotations__', {})
        for base in bases:
            annotations.update(base.__annotations__)

        for field_name, field_cls in annotations.items():
            if (
                not field_name.startswith('__')
                and not is_optional(field_cls)
                and not is_annotated(field_cls)
            ):
                annotations[field_name] = Optional[field_cls]

        namespaces['__annotations__'] = annotations
        namespaces['model_name'] = name
        return super().__new__(cls, name, bases, namespaces, **kwargs)


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
