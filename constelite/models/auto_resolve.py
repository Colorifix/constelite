from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, root_validator, Extra

from constelite.utils import all_subclasses


class AutoResolveBaseModel(BaseModel):
    model_name: Optional[str]

    @root_validator()
    def assign_model(cls, values):
        values['model'] = cls.__name__
        return values


class FlexibleModel(BaseModel, extra=Extra.allow):
    """Flexibe model.

    A fallback model for when model class cannot be resolved.
    """
    def asmodel(self, model: Type):
        return model(**self.__dict__)


def resolve_model(
        values: Dict[str, Any],
        force: bool = False
) -> 'AutoResolveBaseModel':
    """Resolve model class.

    Infers model class name from the `model` key in passed values
    and converts values into the right class object.

    Args:
        values: A dictionary of attributes for a new object.
        force: If `True` will ignore model mismatch errors.

    Returns:
        An object of the class infered from the `values`. If `force`
        is `True` and class name cannot be found will return an
        object of a `FlexibleModel` instead.

    Raises:
        KeyError: If `model` key is not set or missing from `values`
            and `force` is set to `False`.
        ValueError: If model with a class name specified by `model`
            can not be found and `force` is set to `False`.
    """
    model_name = values.pop('model_name', None)

    if model_name is None:
        if force is False:
            raise KeyError("'model' field is missing or empty")
        else:
            return FlexibleModel(**values)

    model_cls = next(
        (
            m for m in all_subclasses(AutoResolveBaseModel)
            if m.__name__ == model_name
        ),
        None
    )

    if model_cls is None:
        if force is False:
            raise ValueError(
                f"Model '{model_name}' is not found"
            )
        else:
            model_cls = FlexibleModel

    for value in values:
        if isinstance(value, dict) and 'model_name' in value:
            values[value] = resolve_model(
                values=values[value],
                force=force
            )
    return model_cls(**values)
