from constelite.models.model import StateModel

from pydantic.v1.generics import GenericModel
from typing import Generic, TypeVar, List, Union


class Object(StateModel):
    name: str


OT = TypeVar('ObjectType')


class ObjectGroup(GenericModel, Generic[OT]):
    objects: Union[List[OT], List['ObjectGroup[OT]']]
