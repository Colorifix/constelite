from typing import TypeVar, Generic, Optional
import uuid

from enum import Enum

from pydantic.v1 import Field, UUID4, BaseModel, validator, root_validator
from pydantic.v1.generics import GenericModel

from constelite.models import StateModel, StoreModel, Ref, resolve_model
from constelite.loggers import LoggerConfig
from constelite.store.queries import PropertyQuery
from constelite.graphql.utils import GraphQLQuery, GraphQLModelQuery

StateModelType = TypeVar('StateModelType')

class ProtocolRequest(GenericModel, Generic[StateModelType]):
    args: StateModelType
    logger: Optional[LoggerConfig] = None

class JobStatus(str, Enum):
    submitted = "submitted"
    success = "success"
    failed = "failed"


Result = TypeVar("Result")


class Job(StateModel, GenericModel, Generic[Result]):
    uid: UUID4 = Field(default_factory=uuid.uuid4)
    status: Optional[JobStatus] = None
    result: Optional[Result] = None
    error: Optional[str] = None

def validate_state(ref: Ref) -> Ref:
    if ref.state is None:
        raise ValueError('Ref state is empty')
    ref = resolve_model(
        values=ref.dict()
    )

    return ref


class RefRequest(BaseModel):
    ref: Ref

    @validator('ref')
    def validate_ref_store(cls, value):
        if value.record is None:
            raise ValueError("Reference has an empty record")
        return value


class PutRequest(BaseModel):
    ref: Ref
    store: Optional[StoreModel]
    _validate_state = validator('ref', allow_reuse=True)(validate_state)

    @root_validator(skip_on_failure=True)
    def root(cls, values):
        store = values.get("store", None)
        ref = values.get("ref", None)

        if store is None and ref.record is None:
            raise ValueError(
                "Unknown store."
                "Either send a reference with a record or supply a store"
            )
        if store is None:
            values['store'] = ref.record.store
        return values


class PatchRequest(RefRequest):
    _validate_state = validator('ref', allow_reuse=True)(validate_state)


class GetRequest(RefRequest):
    store: Optional[StoreModel] = None


class DeleteRequest(RefRequest):
    pass


class QueryRequest(BaseModel):
    query: Optional[PropertyQuery] = None
    model_name: str
    store: StoreModel
    include_states: Optional[bool] = False


class GraphQLQueryRequest(BaseModel):
    query: GraphQLQuery
    store: StoreModel


class GraphQLModelQueryRequest(BaseModel):
    query: GraphQLModelQuery
    store: StoreModel
