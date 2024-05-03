from typing import Optional, Type

import os

import pickle

from pydantic.v1 import Field

from constelite.models import (
    StateModel, UID, resolve_model
)

from constelite.store.uid_key_base import (
    UIDKeyStoreBase
)


class PickleStore(UIDKeyStoreBase):
    path: Optional[str] = Field(exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)

    async def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        path = os.path.join(self.path, uid)
        return os.path.exists(path)

    async def store(self, uid: UID, model: StateModel) -> UID:
        path = os.path.join(self.path, uid)

        exception = None

        with open(path, 'wb') as f:
            try:
                pickle.dump(model.dict(), f)
            except Exception as e:
                exception = e

        if exception is not None:
            os.remove(path)
            raise exception

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
            path = os.path.join(self.path, uid)
            with open(path, 'rb') as f:
                return resolve_model(
                    values=pickle.load(f)
                )

    async def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        if await self.uid_exists(
            uid=uid,
            model_type=model_type
        ):
            path = os.path.join(self.path, uid)
            os.remove(path)