from typing import Generic, List, TypeVar, ForwardRef, Optional
from typing_extensions import Annotated

from pydantic.v1 import BaseModel, Field
from pydantic.v1.generics import GenericModel

from constelite.utils import resolve_forward_ref

from constelite.models.model import StateModel
from constelite.models.ref import Ref

M = TypeVar('Model')


class Relationship(GenericModel, Generic[M]):
    model_type: M

    @classmethod
    def model(cls):
        return cls.__fields__['model_type'].type_

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        MT = cls.__fields__['model_type'].type_
        if isinstance(MT, ForwardRef):
            MT = resolve_forward_ref(MT, StateModel)

        class DummyModel(BaseModel):
            v: List[Ref[MT]]

        if v is None:
            v = []

        dm = DummyModel(v=v)
        assert issubclass(MT, StateModel)
        return dm.v


class Association(Relationship, Generic[M]):
    pass


class Composition(Relationship, Generic[M]):
    pass


class Aggregation(Relationship, Generic[M]):
    pass


class Backref(Relationship, Generic[M]):
    @classmethod
    def validate(cls, v):
        class DummyModel(BaseModel):
            v: List[Ref]

        dm = DummyModel(v=v)
        return dm.v


def backref(model: str, from_field: str):
    return Annotated[Optional[Backref[ForwardRef(model)]], Field(from_field=from_field)]
