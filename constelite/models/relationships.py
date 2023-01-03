from typing import Generic, List, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel

from constelite.models.model import Model

M = TypeVar('Model')


class Relationship(GenericModel, Generic[M]):
    model_type: M

    @classmethod
    @property
    def model(cls):
        return cls.__fields__['model_type'].type_

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        MT = cls.__fields__['model_type'].type_

        class DummyModel(BaseModel):
            v: List[MT]

        dm = DummyModel(v=v)
        assert issubclass(MT, Model)
        return dm.v


class Association(Relationship, Generic[M]):
    pass


class Composition(Relationship, Generic[M]):
    pass


class Aggregation(Relationship, Generic[M]):
    pass


class Backref(Relationship, Generic[M]):
    pass
