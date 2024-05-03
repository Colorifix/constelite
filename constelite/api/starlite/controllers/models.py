from typing import TypeVar, Generic, Optional

import uuid

from pydantic.v1 import Field, UUID4
from pydantic.v1.generics import GenericModel

from constelite.models import StateModel
from constelite.loggers import LoggerConfig

from enum import Enum


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
    status: Optional[JobStatus]
    result: Optional[Result]
    error: Optional[str]
