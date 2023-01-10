from starlite import Controller, post, State

from constelite.models import StateModel, Ref, resolve_model
from constelite.api.starlite.requests import (
    PutRequest, PatchRequest, GetRequest, DeleteRequest
)


class StoreController(Controller):
    path = '/store'

    @post('/put')
    def put(self, data: PutRequest, state: State) -> Ref:
        ref = data.ref
        store = next(
            (
                store for store in state['stores']
                if store.uid == data.store.uid),
            None
        )

        if store is None:
            raise ValueError("Store not found")

        return store.put(ref)

    @post('/patch')
    def patch(self, data: PatchRequest, state: State) -> Ref:
        ref = data.ref

        store = data.get_store(state=state)

        if store is None:
            raise ValueError("Store not found")
        return store.patch(ref)

    @post('/get')
    def get(self, data: GetRequest, state: State) -> StateModel:
        ref = data.ref

        store = data.get_store(state=state)

        if store is None:
            raise ValueError("Store not found")

        return store.get(ref)

    @post('/delete')
    def delete(self, data: DeleteRequest, state: State) -> None:
        ref = data.ref

        store = data.get_store(state=state)

        if store is None:
            raise ValueError("Store not found")
        return store.delete(ref)
