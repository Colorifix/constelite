from typing import Generic, TypeVar, Optional, Any

from pydantic.generics import GenericModel
from pydantic import UUID4, validator

from constelite.models.model import StateModel
from constelite.models.store import StoreRecordModel

M = TypeVar('StateModel')


class Ref(GenericModel, Generic[M]):
    model_name = 'Ref'
    record: Optional[StoreRecordModel]
    guid: Optional[UUID4]
    state: Optional[M]

    state_model_name: Optional[str]

    @property
    def uid(self):
        return self.record.uid

    @validator('state_model_name', always=True)
    def assign_state_type(cls, v, values):
        state = values.get('state', None)
        if v is not None and state is None:
            return v
        if cls.__fields__['state'].type_ != Any:
            return cls.__fields__['state'].type_.__name__
        else:
            if (
                cls.__fields__['state'].type_ == Any
                and state is not None
            ):
                return state.__class__.__name__
            else:
                return 'Any'

    def strip(self):
        return Ref(
            record=self.record,
            guid=self.guid,
            state=None
        )

    def get_state(self, cache=True):
        if self.state is not None:
            state = self.state
        else:
            if self.record is not None:

                from constelite.api import ConsteliteAPI

                api = ConsteliteAPI.api

                store = next(
                    (store for store in api.stores if store.uid == self.uid),
                    None
                )

                if store is None:
                    raise ValueError(
                        "Environment api does not have"
                        f"a {self.record.store.name} store("
                        f"{self.record.store.uid})"
                    )

                state = store.get(self).state
                if cache is True:
                    self.state = state

        return state


def ref(model: StateModel, guid: Optional[UUID4] = None):
    return Ref(
        state=model
    )
