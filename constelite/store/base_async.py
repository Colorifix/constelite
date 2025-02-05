import asyncio

from typing import (
    Dict,
    List,
    Optional,
    Literal,
    ClassVar,
    Callable,
    Type,
    Any,
    ForwardRef
)

from pydantic.v1 import BaseModel, root_validator, PrivateAttr, UUID4, AnyUrl

from constelite.graphql.schema import GraphQLSchemaManager
from constelite.graphql.utils import GraphQLQuery, GraphQLModelQuery
from constelite.utils import async_map

from constelite.models import (
    StateModel,
    Ref,
    StaticTypes,
    Dynamic,
    RelInspector,
    StateInspector,
    StoreModel,
    StoreRecordModel,
    UID,
    get_auto_resolve_model
)

GUIDMap = ForwardRef("GUIDMap")


class Query(BaseModel):
    # include_static: Optional[bool] = True
    # include_dynamic: Optional[bool] = True
    # include_associations: Optional[bool] = False
    # include_compositions: Optional[bool] = True
    # include_aggregations: Optional[bool] = True
    pass


class RefQuery(Query):
    ref: Ref


class BackrefQuery(RefQuery):
    class_name: str
    backref_field_name: str


class PropertyQuery(Query):
    property_values: Dict[str, Any]

    def __init__(self, **data):
        property_values = data.pop('property_values', None)
        if property_values is None:
            super().__init__(property_values=data)
        else:
            super().__init__(property_values=property_values)


class GetAllQuery(Query):
    pass


StoreMethod = Literal['PUT', 'PATCH', 'GET', 'DELETE', 'QUERY', "GRAPHQL"]


class AsyncBaseStore(StoreModel):
    _allowed_methods: ClassVar[
        List[StoreMethod]] = []

    _guid_map: Optional[GUIDMap] = PrivateAttr(default=None)

    graphql_schema_manager: Optional[GraphQLSchemaManager] = None

    class Config:
        arbitrary_types_allowed = True

    def set_guid_map(self, guid_map: GUIDMap):
        self._guid_map = guid_map

    def disable_guid(self):
        self._guid_map = None

    async def get_guid_record(self, uid: UID):
        if self._guid_map is not None:
            guid = await self._guid_map.get_guid(
                uid=uid,
                store=self
            )
            if guid is None:
                guid = await self._guid_map.create_guid(
                    uid=uid,
                    store=self
                )
            return guid

    async def link_record(self, uid: UID, guid: UUID4):
        if self._guid_map is not None:
            existing_guid = await self._guid_map.get_guid(uid=uid, store=self)

            if existing_guid is not None:
                if existing_guid != guid:
                    raise ValueError('GUID mismatch')
                else:
                    return
            if await self._guid_map.guid_exists(guid=guid):
                await self._guid_map.link_uid(uid=uid, guid=guid, store=self)
            else:
                raise ValueError(
                    f'Could not find entity {guid} in the guid map'
                )

    async def delete_uid_record(self, uid: UID):
        if self._guid_map is not None:
            await self._guid_map.delete_uid(
                uid=uid,
                store=self
            )

    @root_validator(pre=True)
    def assign_name(cls, values):
        name = values.get('name')
        if name is None:
            values['name'] = cls.__name__
        return values

    async def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        raise NotImplementedError

    async def create_model(
            self,
            model_type: Type[StateModel],
            static_props: Dict[str, StaticTypes],
            dynamic_props: Dict[str, Optional[Dynamic]]) -> UID:
        raise NotImplementedError

    async def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        raise NotImplementedError

    async def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]) -> None:
        raise NotImplementedError

    async def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        raise NotImplementedError

    async def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        raise NotImplementedError

    async def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str) -> List[UID]:
        raise NotImplementedError

    async def create_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            inspector: RelInspector) -> None:
        raise NotImplementedError

    async def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        raise NotImplementedError

    async def get_model_by_backref(self, query: BackrefQuery) -> List[StateModel]:
        raise NotImplementedError

    async def execute_query(
            self,
            query: Optional[Query],
            model_type: Type[StateModel],
            include_states: bool
    ) -> Dict[UID, Optional[StateModel]]:
        raise NotImplementedError

    async def generate_ref(
        self,
        uid: UID,
        state_model_name: Optional[str] = None,
        state: Optional[StateModel] = None,
        guid: Optional[UUID4] = None,
        url: Optional[AnyUrl] = None
    ):

        if guid is None:
            guid = await self.get_guid_record(
                uid=uid
            )
        else:
            await self.link_record(uid=uid, guid=guid)

        if guid is not None:
            guid = str(guid)

        return Ref(
            record=StoreRecordModel(
                store=self.dict(),
                uid=uid,
                url=url
            ),
            state=state,
            state_model_name=state_model_name,
            guid=guid
        )

    async def _validate_ref_uid(self, ref: Ref):
        if ref.record is None:
            raise ValueError("Can't validate uid of a ref without a record")

        model_name = ref.state_model_name
        if model_name is None:
            raise ValueError("Unspecified ref.state_model_name")

        state_model_type = get_auto_resolve_model(
            model_name=model_name,
            root_cls=StateModel
        )

        uid_exists = await self.uid_exists(
            uid=ref.uid,
            model_type=state_model_type
        )

        if not uid_exists:
            raise KeyError('Ref does not exist in the store')

    async def _validate_ref_full(self, ref: Ref) -> Ref:
        ref = await self._fetch_record_by_guid(ref)

        if ref.record is None:
            raise ValueError("Reference does not have a store record")
        if ref.record.store.uid != self.uid:
            raise ValueError(
                'Reference store record is from a different store'
            )
        await self._validate_ref_uid(ref=ref)
        return ref

    async def _fetch_record_by_guid(self, ref: Ref) -> Ref:
        if ref.guid is not None and self._guid_map is not None:
            uid = await self._guid_map.get_uid(guid=ref.guid, store=self)
            # Copy the ref before changing it.
            ref = ref.copy_ref()
            if uid is not None:
                ref.record = StoreRecordModel(
                    store=self,
                    uid=uid
                )
            else:
                ref.record = None
        return ref

    def _validate_method(self, method: StoreMethod):
        if method not in self._allowed_methods:
            raise NotImplementedError(
                f'{method} is not allowed for {self.name}'
            )

    async def _update_relationships(
            self,
            method: Callable,
            from_uid: UID,
            from_model_type: Type[StateModel],
            field_name: str,
            rel: RelInspector,
            overwrite: bool = False,
            delete_orphans: bool = False):

        if overwrite is True:
            orphans = await self.delete_all_relationships(
                from_uid=from_uid,
                from_model_type=from_model_type,
                rel_from_name=field_name
            )

            if delete_orphans is True:
                async with asyncio.TaskGroup() as tg:
                    for orphan_uid in orphans:
                        tg.create_task(
                            self.delete_model(
                                uid=orphan_uid,
                                model_type=from_model_type
                            )
                        )
        
        tasks = []
        async with asyncio.TaskGroup() as tg:
            for to_ref in rel.to_refs:
                task = tg.create_task(
                    method(ref=to_ref)
                )
                tasks.append(task)

        rel.to_refs = [
            task.result() for task in tasks
        ]

        await self.create_relationships(
            from_uid=from_uid,
            from_model_type=from_model_type,
            inspector=rel
        )

    async def put(self, ref: Ref) -> Ref:
        self._validate_method('PUT')
        ref = await self._fetch_record_by_guid(ref)

        # For put inside _update_relations when relationship is a
        # reference to existing state
        if ref.state is None:
            await self._validate_ref_uid(ref)
            return ref

        inspector = StateInspector.from_state(ref.state)

        if ref.record is None:
            uid = await self.create_model(
                model_type=inspector.model_type,
                static_props=inspector.static_props,
                dynamic_props=inspector.dynamic_props
            )

            async with asyncio.TaskGroup() as tg:
                for field_name, rel in (
                    inspector.associations | inspector.aggregations
                    | inspector.compositions
                ).items():
                    tg.create_task(
                            self._update_relationships(
                            method=self.put,
                            from_uid=uid,
                            from_model_type=inspector.model_type,
                            field_name=field_name,
                            rel=rel
                        )
                    )

            return await self.generate_ref(
                uid=uid,
                state_model_name=ref.state_model_name,
                guid=ref.guid
            )

        else:
            ref = await self._validate_ref_full(ref)
            await self.overwrite_static_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.static_props
            )
            await self.overwrite_dynamic_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.dynamic_props
            )

            async with asyncio.TaskGroup() as tg:
                for field_name, rel in (
                        inspector.associations | inspector.aggregations).items():
                    tg.create_task(
                        self._update_relationships(
                            method=self.put,
                            from_uid=ref.uid,
                            from_model_type=inspector.model_type,
                            field_name=field_name,
                            rel=rel,
                            overwrite=True,
                            delete_orphans=False
                        )
                    )

                for field_name, rel in inspector.compositions.items():
                    tg.create_task(
                        self._update_relationships(
                            method=self.put,
                            from_uid=ref.uid,
                            from_model_type=inspector.model_type,
                            field_name=field_name,
                            rel=rel,
                            overwrite=True,
                            delete_orphans=True
                        )
                    )
            return await self.generate_ref(
                uid=ref.uid,
                state_model_name=ref.state_model_name,
                guid=ref.guid
            )

    async def patch(self, ref: Ref) -> Ref:
        self._validate_method('PATCH')
        ref = await self._validate_ref_full(ref=ref)

        if ref.state is None:
            return ref

        inspector = StateInspector.from_state(ref.state)

        if inspector.static_props != {}:
            await self.overwrite_static_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.static_props
            )
        if inspector.dynamic_props != {}:
            await self.extend_dynamic_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.dynamic_props
            )

        async with asyncio.TaskGroup() as tg:

            for field_name, rel in inspector.associations.items():
                tg.create_task(
                    self._update_relationships(
                        method=self.patch,
                        from_uid=ref.uid,
                        from_model_type=inspector.model_type,
                        field_name=field_name,
                        rel=rel,
                        overwrite=True,
                        delete_orphans=False
                    )
                )

            for field_name, rel in (
                    inspector.compositions | inspector.aggregations).items():
                tg.create_task(
                    self._update_relationships(
                        method=self.patch,
                        from_uid=ref.uid,
                        from_model_type=inspector.model_type,
                        field_name=field_name,
                        rel=rel
                    )
                )

        return await self.generate_ref(
            uid=ref.uid,
            state_model_name=ref.state_model_name,
            guid=ref.guid
        )

    async def delete(self, ref: Ref) -> None:
        self._validate_method('DELETE')

        ref = await self._validate_ref_full(ref=ref)

        model_type = get_auto_resolve_model(
            model_name=ref.state_model_name
        )

        if model_type is None:
            raise ValueError(
                "Unknown state model name '{ref.state_model_name}'"
            )

        state = await self.get_state_by_uid(
            uid=ref.uid,
            model_type=model_type
        )

        inspector = StateInspector.from_state(state)

        async def delete_rels_with_orphans_wrapper(field_name, rel):
            orphan_uids = await self.delete_all_relationships(
                from_uid=ref.uid,
                from_model_type=model_type,
                rel_from_name=field_name
            )
            async with asyncio.TaskGroup() as tg:
                for orphan_uid in orphan_uids:
                    tg.create_task(
                            self.delete_model(
                            uid=orphan_uid,
                            model_type=rel.to_model
                        )
                    )

        async with asyncio.TaskGroup() as tg:
            for field_name, rel in (
                        inspector.associations | inspector.aggregations).items():
                tg.create_task(
                    self.delete_all_relationships(
                        from_uid=ref.uid,
                        from_model_type=model_type,
                        rel_from_name=field_name
                    )
                )

            for field_name, rel in inspector.compositions.items():
                tg.create_task(
                    delete_rels_with_orphans_wrapper(
                        field_name=field_name,
                        rel=rel
                    )
                )

        await self.delete_uid_record(uid=ref.uid)

        await self.delete_model(
            uid=ref.uid,
            model_type=model_type
        )

    async def get(self, ref: Ref) -> Ref:
        self._validate_method('GET')
        ref = await self._validate_ref_full(ref)

        if ref.state_model_name == 'Any':
            model_type = Any
        else:
            model_type = get_auto_resolve_model(
                model_name=ref.state_model_name
            )
        state = await self.get_state_by_uid(
            uid=ref.uid,
            model_type=model_type
        )

        return await self.generate_ref(
            uid=ref.record.uid,
            state=state
        )

    async def bulk_get(self, refs: list[Ref]) -> list[Ref]:
        self._validate_method('GET')
        return await async_map(self.get, refs)

    async def query(
        self,
        model_name: str,
        include_states: bool,
        query: Optional[Query] = None
    ) -> List[Ref]:
        self._validate_method('QUERY')
        model_type = get_auto_resolve_model(
            model_name=model_name,
            root_cls=StateModel
        )

        if model_type is None:
            raise ValueError(f"Unknown model '{model_name}'")

        uids = await self.execute_query(
            query=query,
            model_type=model_type,
            include_states=include_states
        ) 

        tasks = []

        async with asyncio.TaskGroup() as tg:
            for uid, state in uids.items():
                task =  tg.create_task(
                    self.generate_ref(
                        uid=uid,
                        state_model_name=model_name,
                        state=state
                    )
                )

                tasks.append(task)
        
        refs = [
            task.result() for task in tasks
        ]

        return refs

    async def execute_graphql(self, query: GraphQLQuery) -> Dict[str, Any]:
        """
        Executes a GraphQL query using the GraphQL schema. Generates a set of
        dataloaders to use in the query.

        Args:
            query: Query to be executed

        Returns:
            Data in the form of a GraphQL response dictionary.
        """
        # Get the GraphQL schema
        schema = self.graphql_schema_manager.get_schema()
        # Generate a new set of data loaders for this store
        dataloaders = self.graphql_schema_manager.get_dataloaders(self)
        results = await schema.execute_async(
            query.query_string,
            context={'store': self, 'dataloaders': dataloaders}
        )

        return results.formatted

    async def graphql(self, query: GraphQLQuery) -> Dict[str, Any]:
        """
        Runs a GraphQL query and return the data in the form of a GraphQL
        response dictionary.

        Args:
            query: Query to be executed

        Returns:
            Data in the form of a GraphQL response dictionary.
        """
        self._validate_method('GRAPHQL')
        return await self.execute_graphql(query)

    async def graphql_models(self, query: GraphQLModelQuery) -> List[Ref]:
        """
        Runs a GraphQL query and return the data in the form of a list of
        Ref models.

        Args:
            query: Query to be executed

        Returns:
            List of references to the records that match the query.
        """
        self._validate_method('GRAPHQL')
        results = await self.execute_graphql(
            query
        )
        if 'data' in results:
            values = list(results['data'].values())
            if len(values) > 1:
                raise NotImplemented(
                    "Not expecting multiple GraphQL queries"
                )
            return values[0]
        else:
            return results.formatted
