from typing import Optional, Type, Dict

from pydantic.v1 import Field

from constelite.models import (
    StateModel, UID
)

from constelite.store.uid_key_base import (
    UIDKeyStoreBase
)


class MemoryStore(UIDKeyStoreBase):
    path: Optional[str] = Field(exclude=True)
    memory: Optional[Dict] = Field(exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.memory = {}

    def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        return uid in self.memory

    def store(self, uid: UID, model: StateModel) -> UID:
        self.memory[uid] = model

        return uid

    def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        if not self.uid_exists(
            uid=uid,
            model_type=model_type
        ):
            raise ValueError(f"Model with reference '{uid}' cannon be found")
        else:
            return self.memory[uid]

    def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        if self.uid_exists(
            uid=uid,
            model_type=model_type
        ):
            self.memory.pop(uid)
