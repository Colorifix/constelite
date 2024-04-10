from typing import Any
from litestar import Controller, post

from constelite.models import StateModel, Ref
from constelite.api.starlite.requests import (
    PutRequest, PatchRequest, GetRequest, DeleteRequest,
    QueryRequest
)


class StoreController(Controller):
    path = '/store'
    tags = ["Store"]

    @post('/put', summary="Put", sync_to_thread=True)
    def put(self, data: PutRequest, api: Any) -> Ref:
        """
        Put will attemp to create a new record in the store provided.

        If passed reference has `record` defined, it will attempt to
        overwrite the existing record with the provided state.
        """
        ref = data.ref
        store = api.get_store(data.store.uid)

        if store is None:
            raise ValueError("Store not found")

        return store.put(ref)

    @post('/patch', summary="Patch", sync_to_thread=True)
    def patch(self, data: PatchRequest, api: Any) -> Ref:
        """
        Patch will attemp update an existing store record.

        All static properties will be overwritten along with any
        `Association` type relationships.

        Dynamic properties will be extended with the time points
        provided in the state, so will any `Composition` and
        `Aggregation` type relationships.
        """
        ref = data.ref

        store = api.get_store(ref.record.store.uid)

        if store is None:
            raise ValueError("Store not found")
        return store.patch(ref)

    @post('/get', summary="Get", sync_to_thread=True)
    def get(self, data: GetRequest, api: Any) -> StateModel:
        """
        Get will try to retrieve a state of the existing record.
        """
        ref = data.ref
        if data.store is None:
            store_uid = ref.record.store.uid
        else:
            store_uid = data.store.uid

        store = api.get_store(store_uid)

        if store is None:
            raise ValueError("Store not found")

        return store.get(ref)

    @post('/delete', summary="Delete", sync_to_thread=True)
    def delete(self, data: DeleteRequest, api: Any) -> None:
        """
        Delete will delete the existing record along with
        the records linked by a `Composition` type relationship.
        """
        ref = data.ref

        store = api.get_store(ref.record.store.uid)

        if store is None:
            raise ValueError("Store not found")
        return store.delete(ref)

    @post('/query', summary="Query", sync_to_thread=True)
    def query(self, data: QueryRequest, api: Any) -> None:
        """
        Query will return store records mathing the query parameters.
        """
        store = api.get_store(data.store.uid)
        if store is None:
            raise ValueError("Store not found")

        return store.query(
            query=data.query,
            model_name=data.model_name,
            include_states=data.include_states
        )
