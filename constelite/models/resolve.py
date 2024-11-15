from typing import Dict, Any, Optional, Type, TypeVar

from constelite.utils import all_subclasses
from constelite.models import AutoResolveBaseModel, Ref, FlexibleModel


def get_auto_resolve_model(model_name: str, root_cls=AutoResolveBaseModel):
    model_type = next(
        (
            m for m in all_subclasses(root_cls)
            if m.__name__ == model_name
        ),
        None
    )

    return model_type


ModelType = TypeVar('ModelType')


def resolve_model(
        values: Dict[str, Any],
        force: bool = False,
        model_type: Optional[Type[ModelType]] = None
) -> ModelType:
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
    if not model_type:
        model_name = values.pop('model_name', None)

        if model_name is None:
            if force is False:
                raise KeyError("'model_name' field is missing or empty")
            else:
                return FlexibleModel(**values)

        if model_name == "Ref":
            model_type = Ref
        else:
            model_type = get_auto_resolve_model(model_name=model_name)
    
    if model_type is None:
        if force is False:
            raise ValueError(
                f"Model '{model_name}' is not found"
            )
        else:
            model_type = FlexibleModel

    for key, value in values.items():
        if isinstance(value, dict) and 'model_name' in value:
            values[key] = resolve_model(
                values=values[key],
                force=force
            )
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict) and 'model_name' in item:
                    value[i] = resolve_model(values=item, force=force)
    return model_type(**values)
