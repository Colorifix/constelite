from pydantic import BaseModel, Extra, root_validator
from typing import Type, Optional, Any, Dict

from constelite import get_store, Ref


class Model(BaseModel):
    """A base model for all constelite models.

    Attrs:
        model: A name of the model class.
        ref: Reference to the object in store.
    """
    ref: Optional[Ref]
    model: str

    @root_validator(pre=True)
    def validate_ref(cls, values):
        if 'ref' in values and values['ref'] is not None:
            store = get_store()
            model = store.load(Ref(ref=values['ref']))
            return model.dict()
        values['model'] = cls.__name__
        return values

    @classmethod
    def _submodels(cls):
        for sub_cls in cls.__subclasses__():
            yield sub_cls
            for sub_sub_cls in sub_cls._submodels():
                yield sub_sub_cls

    @classmethod
    def resolve(cls, values: Dict[str, Any], force: bool = False) -> 'Model':
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
        model_name = values.pop('model', None)

        if model_name is None:
            if force is False:
                raise KeyError("'model' field is missing or empty")
            else:
                return FlexibleModel(**values)

        model_cls = next(
            (m for m in cls._submodels() if m.__name__ == model_name),
            None
        )

        if model_cls is None:
            if force is False:
                raise ValueError(
                    f"Model '{model_name}' is not found"
                )
            else:
                model_cls = FlexibleModel
        return model_cls(**values)


class FlexibleModel(Model, extra=Extra.allow):
    """Flexibe model.

    A fallback model for when model class cannot be resolved.
    """
    def asmodel(self, model: Type[Model]):
        return model(**self.__dict__)
