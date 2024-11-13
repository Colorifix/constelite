from typing import Optional
from constelite.models.auto_resolve import AutoResolveBaseModel
from pydantic.v1 import UUID4, BaseModel, AnyUrl

UID = str


class StoreModel(BaseModel):
    uid: UUID4
    name: Optional[str]


class StoreRecordModel(BaseModel):
    store: StoreModel
    uid: UID
    url: Optional[AnyUrl] = None
