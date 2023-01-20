from typing import Generic, TypeVar, Optional, Any, Union

from pydantic.generics import GenericModel
from pydantic import UUID4, validator, validate_arguments

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
        if v is not None:
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

    def __getattr__(self, key):
        if hasattr(self.state, key):
            return getattr(self.state, key)
        else:
            raise AttributeError

    def __setattr__(self, key, value):
        if key in self.__dict__:
            super().__setattr__(key, value)
        else:
            if self.state is None:
                from constelite.models.resolve import get_auto_resolve_model

                state_model = get_auto_resolve_model(
                    self.state_model_name, StateModel
                )

                self.state = state_model()
            setattr(self.state, key, value)


@validate_arguments
def ref(model: Union[StateModel, Ref], guid: Optional[UUID4] = None):
    if isinstance(model, StateModel):
        state = model
    else:
        state = model.state
    return Ref(
        state=state
    )
