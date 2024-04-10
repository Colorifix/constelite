from typing import Type, Optional
from pydantic.v1 import Field

from constelite.models import (
    StateModel, UID, resolve_model
)

from constelite.store.uid_key_base import UIDKeyStoreBase

from pymemcache.client.base import Client
from pymemcache import serde


class MemcachedStore(UIDKeyStoreBase):
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE"]
    host: Optional[str] = Field(exclude=True)
    client: Optional[Client] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.client = Client(self.host, serde=serde.pickle_serde)

    def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        model = self.client.get(uid)
        return model is not None

    def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        if not self.uid_exists(
            uid=uid,
            model_type=model_type
        ):
            raise ValueError(f"Model with reference '{uid}' cannot be found")
        else:
            model = self.client.get(uid)
            return resolve_model(values=model)

    def store(self, uid: str, model: StateModel) -> str:
        self.client.set(uid, model.dict())

        return uid

    def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        if self.uid_exists(
            uid=uid,
            model_type=model_type
        ):
            self.client.delete(uid)

