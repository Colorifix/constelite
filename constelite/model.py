from pydantic import BaseModel, Extra, root_validator
from typing import Type, Optional

from constelite import get_store, Ref


class Model(BaseModel):
    ref: Optional[Ref]

    @root_validator(pre=True)
    def validate_ref(cls, values):
        if 'ref' in values and values['ref'] is not None:
            store = get_store()
            model = store.load(Ref(ref=values['ref']))
            return model.dict()
        return values


class FlexibleModel(Model, extra=Extra.allow):
    def asmodel(self, model: Type[Model]):
        return model(**self.__dict__)
