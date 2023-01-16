from typing import Any
from starlite import Controller, post, State

from constelite.models import StateModel, Ref, resolve_model
from constelite.api.starlite.requests import (
    PutRequest, PatchRequest, GetRequest, DeleteRequest
)


class StoreController(Controller):
    path = '/store'

    @post('/put')
    def put(self, data: PutRequest, api: Any) -> Ref:
        ref = data.ref
        store = api.get_store(data.store.uid)

        if store is None:
            raise ValueError("Store not found")

        return store.put(ref)

    @post('/patch')
    def patch(self, data: PatchRequest, api: Any) -> Ref:
        ref = data.ref

        store = api.get_store(ref.record.store.uid)

        if store is None:
            raise ValueError("Store not found")
        return store.patch(ref)

    @post('/get')
    def get(self, data: GetRequest, api: Any) -> StateModel:
        ref = data.ref

        store = api.get_store(ref.record.store.uid)

        if store is None:
            raise ValueError("Store not found")

        return store.get(ref)

    @post('/delete')
    def delete(self, data: DeleteRequest, api: Any) -> None:
        ref = data.ref

        store = api.get_store(ref.record.store.uid)

        if store is None:
            raise ValueError("Store not found")
        return store.delete(ref)
