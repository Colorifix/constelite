from constelite.models.model import Model

from pydantic.generics import GenericModel
from typing import Generic, TypeVar, List, Union


class Object(Model):
    name: str


OT = TypeVar('ObjectType')


class ObjectGroup(GenericModel, Generic[OT]):
    objects: Union[List[OT], List['ObjectGroup[OT]']]
