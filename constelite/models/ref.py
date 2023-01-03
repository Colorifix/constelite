from typing import Generic, TypeVar, Optional

from pydantic.generics import GenericModel
from pydantic import UUID4

from constelite.models.store import StoreRecordModel

M = TypeVar('StateModel')


class Ref(GenericModel, Generic[M]):

    @property
    def uid(self):
        return self.record.uid

    record: Optional[StoreRecordModel]
    guid: Optional[UUID4]
    state: Optional[M]

    def strip(self):
        return Ref(
            record=self.record,
            guid=self.guid,
            state=None
        )
