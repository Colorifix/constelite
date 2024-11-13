from __future__ import annotations

from typing import Generic, TypeVar, Optional, Any, Union, Type, Self
from copy import deepcopy

from pydantic.v1.generics import GenericModel
from pydantic.v1 import UUID4, validator, validate_arguments, AnyUrl

from constelite.models.model import StateModel
from constelite.models.store import StoreRecordModel, StoreModel


StateModelType = TypeVar('StateModelType')

class Ref(GenericModel, Generic[StateModelType]):
    """
    Reference to a record in the store.

    Attributes:
        record: Record metadata. Contains the unique identifier of the record and the store.
        state: State of the record.
        state_model_name: Name of the state model of the record.
        guid: Global identifier of the entity that the record belongs to.
    """
    model_name = 'Ref'
    record: Optional[StoreRecordModel]
    guid: Optional[UUID4]
    state: Optional[StateModelType]

    state_model_name: Optional[str]

    @property
    def uid(self):
        """
        Unique identifier of the record.
        """
        if self.record:
            return self.record.uid
        else:
            raise AttributeError("Can't get uid from reference without a  record")

    @property
    def store_uid(self):
        return self.record.store.uid

    @validator('state_model_name', always=True)
    def assign_state_type(cls, v, values):
        state = values.get('state', None)
        if v is not None:
            if (
                cls.__fields__['state'].type_ != Any
            ):
                from constelite.models.resolve import get_auto_resolve_model
                resolved_cls = get_auto_resolve_model(v)
                if resolved_cls is None:
                    raise ValueError(f"Unknown state model name '{v}'")
                if not issubclass(resolved_cls, cls.__fields__['state'].type_):
                    raise ValueError(f"State model mismatch: expected {cls.__fields__['state'].type_.__name__}, got {resolved_cls.__name__}")

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

    def strip(self) -> Ref[StateModelType]:
        """
        Strips state from the reference.
        
        Returns:
            A copy of the reference without the state.
        """
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

    def copy_ref(self):
        """
        The store may contain sockets (in the case of NeoFlux at least).
        This is not compatible with normal deep copy.
        Not overwriting __copy__ or __deepcopy__ methods because this function
        is somewhere between the two.

        Returns:
            A copy of the class.
            Somewhere between a shallow copy and a deepcopy.
        """
        try:
            return deepcopy(self)
        except TypeError as e:
            # Can use the same store, just can't copy it.
            # Copy everything else and just move the store across.
            store = self.record.store
            self.record.store = None
            new_ref = deepcopy(self)
            self.record.store = store
            new_ref.record.store = store
            return new_ref


@validate_arguments
def ref(
        model: Union[StateModel, Ref, Type[StateModel]],
        uid: Optional[str] = None,
        store: Optional[StoreModel] = None,
        guid: Optional[UUID4] = None,
        url: Optional[AnyUrl] = None
) -> Self:
    """
    Generates a reference from either state, reference of state model type.

    Arguments:
        model: State model or reference to state model.
        uid: Unique identifier of the record.
        store: Store to which the record belongs.
        guid: Global identifier of the entity that the record belongs to. Currently not used.
        url: Web URL for accessing the entity outside of Constelite.
    
    Returns:
        A reference to the record.
    """
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
            store=store,
            url=url
        )
    else:
        record = None
    return Ref(
        state=state,
        record=record,
        state_model_name=state_model_name
    )
