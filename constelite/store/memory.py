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
    memory: Optional[Dict] = Field(exclude=True, default=None)

    def __init__(self, **data):
        super().__init__(**data)
        self.memory = {}

    async def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        return uid in self.memory

    async def store(self, uid: UID, model: StateModel) -> UID:
        self.memory[uid] = model

        return uid

    async def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        if not await self.uid_exists(
            uid=uid,
            model_type=model_type
        ):
            raise ValueError(f"Model with reference '{uid}' cannon be found")
        else:
            return self.memory[uid]

    async def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        if await self.uid_exists(
            uid=uid,
            model_type=model_type
        ):
            self.memory.pop(uid)
