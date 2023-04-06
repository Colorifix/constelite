from typing import Generic, TypeVar, Optional, Any, Union, Type

from pydantic.generics import GenericModel
from pydantic import UUID4, validator, validate_arguments

from constelite.models.model import StateModel
from constelite.models.store import StoreRecordModel, StoreModel

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
            state=None,
            state_model_name=self.state_model_name
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
def ref(
        model: Union[StateModel, Ref, Type[StateModel]],
        uid: Optional[str] = None,
        store: Optional[StoreModel] = None,
        guid: Optional[UUID4] = None
):
    state_model_name = None
    if isinstance(model, StateModel):
        state = model
    elif isinstance(model, Ref):
        state = model.state
    else:
        state = None
        state_model_name = model.__name__

    if uid is not None and store is not None:
        record = StoreRecordModel(
            uid=uid,
            store=store
        )
    else:
        record = None
    return Ref(
        state=state,
        record=record,
        state_model_name=state_model_name
    )
