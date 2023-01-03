from constelite.models.auto_resolve import AutoResolveBaseModel
from pydantic import UUID4

UID = str


class StoreModel(AutoResolveBaseModel):
    uid: UUID4
    name: str


class StoreRecordModel(AutoResolveBaseModel):
    store: StoreModel
    uid: UID
