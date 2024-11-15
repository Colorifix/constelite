from typing import Any

from pydantic.v1 import UUID4

from litestar import Controller, post
from litestar.exceptions import HTTPException

from constelite.models import StateModel, Ref
from constelite.store import AsyncBaseStore, BaseStore
from constelite.api.starlite.controllers.models import (
    PutRequest, PatchRequest, GetRequest, DeleteRequest,
    QueryRequest, GraphQLQueryRequest, GraphQLModelQueryRequest
)

from constelite.api.starlite.api import StarliteAPI

def get_store_or_raise_error(api: StarliteAPI, uid: UUID4) -> AsyncBaseStore | BaseStore:
    try:
        store = api.get_store(uid)
        return store
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="Bad request",
            extra={
                "error_message": repr(e)
            }
        )

class StoreController(Controller):
    path = '/store'
    tags = ["Store"]

    @post('/put', summary="Put")
    async def put(self, data: PutRequest, api: StarliteAPI) -> Ref:
        """
        Put will attempt to create a new record in the store provided.

        If passed reference has `record` defined, it will attempt to
        overwrite the existing record with the provided state.
        """
        ref = data.ref
        
        store = get_store_or_raise_error(api, data.store.uid)

        try:
            return await store.put(ref)
        except Exception as e:
            raise HTTPException(
                extra={
                    "error_message": repr(e)
                }
            )

    @post('/patch', summary="Patch")
    async def patch(self, data: PatchRequest, api: StarliteAPI) -> Ref:
        """
        Patch will attemp update an existing store record.

        All static properties will be overwritten along with any
        `Association` type relationships.

        Dynamic properties will be extended with the time points
        provided in the state, so will any `Composition` and
        `Aggregation` type relationships.
        """
        ref = data.ref

        store = get_store_or_raise_error(api, ref.record.store.uid)

        try:
            return await store.patch(ref)
        except Exception as e:
            raise HTTPException(
                extra={
                    "error_message": repr(e)
                }
            )

    @post('/get', summary="Get")
    async def get(self, data: GetRequest, api: StarliteAPI) -> StateModel:
        """
        Get will try to retrieve a state of the existing record.
        """
        ref = data.ref
        if data.store is None:
            store_uid = ref.record.store.uid
        else:
            store_uid = data.store.uid

        store = get_store_or_raise_error(api, store_uid)

        try:
            return await store.get(ref)
        except Exception as e:
            raise HTTPException(
                extra={
                    "error_message": repr(e)
                }
            )

    @post('/delete', summary="Delete")
    async def delete(self, data: DeleteRequest, api: StarliteAPI) -> None:
        """
        Delete will delete the existing record along with
        the records linked by a `Composition` type relationship.
        """
        ref = data.ref

        store = get_store_or_raise_error(api, ref.record.store.uid)
        
        try:
            return await store.delete(ref)
        except Exception as e:
            raise HTTPException(
                extra={
                    "error_message": repr(e)
                }
            )

    @post('/query', summary="Query")
    async def query(self, data: QueryRequest, api: StarliteAPI) -> list[Ref]:
        """
        Query will return store records matching the query parameters.
        """
        store = get_store_or_raise_error(api, data.store.uid)

        try:
            return await store.query(
                query=data.query,
                model_name=data.model_name,
                include_states=data.include_states
            )
        except Exception as e:
            raise HTTPException(
                extra={
                    "error_message": repr(e)
                }
            )

    @post('/graphql', summary="GraphQL")
    async def graphql(self, data: GraphQLQueryRequest, api: StarliteAPI) -> dict[str, Any]:
        """
        Runs a GraphQL query from a string definition.
        Returns the GraphQl results as a dictionary - no conversion to
        Constelite models
        """
        store = get_store_or_raise_error(api, data.store.uid)

        try:
            return await store.graphql(
                query=data.query
            )
        except Exception as e:
            raise HTTPException(
                extra={
                    "error_message": repr(e)
                }
            )

    @post('/graphql_models', summary="GraphQLModels")
    async def graphql_models(self, data: GraphQLModelQueryRequest, api: StarliteAPI) -> list[Ref]:
        """
        Creates a GraphQL query string from the given request.
        Converts the results into Refs and StateModels
        """
        store = get_store_or_raise_error(api, data.store.uid)

        try:
            return await store.graphql_models(
                query=data.query
            )
        except Exception as e:
            raise HTTPException(
                extra={
                    "error_message": repr(e)
                }
            )
