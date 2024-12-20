from typing import (
    Dict,
    List,
    Optional,
    Literal,
    ClassVar,
    Callable,
    Type,
    Any,
    ForwardRef,
    TypeVar
)

from functools import partial

from pydantic.v1 import root_validator, PrivateAttr, UUID4, AnyUrl

from constelite.utils import all_subclasses, to_thread, async_map
from constelite.store.queries import Query, BackrefQuery

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
from constelite.graphql.schema import GraphQLSchemaManager
from constelite.graphql.utils import GraphQLQuery, GraphQLModelQuery


M = TypeVar("M")

GUIDMap = ForwardRef("GUIDMap")

StoreMethod = Literal['PUT', 'PATCH', 'GET', 'DELETE', 'QUERY', "GRAPHQL"]


class BaseStore(StoreModel):
    """
    Base class for all stores.
    """
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

    def get_guid_record(self, uid: UID):
        if self._guid_map is not None:
            guid = self._guid_map.get_guid(
                uid=uid,
                store=self
            )
            if guid is None:
                guid = self._guid_map.create_guid(
                    uid=uid,
                    store=self
                )
            return guid

    def link_record(self, uid: UID, guid: UUID4):
        if self._guid_map is not None:
            existing_guid = self._guid_map.get_guid(uid=uid, store=self)

            if existing_guid is not None:
                if existing_guid != guid:
                    raise ValueError('GUID mismatch')
                else:
                    return
            if self._guid_map.guid_exists(guid=guid):
                self._guid_map.link_uid(uid=uid, guid=guid, store=self)
            else:
                raise ValueError(
                    f'Could not find entity {guid} in the guid map'
                )

    def delete_uid_record(self, uid: UID):
        if self._guid_map is not None:
            self._guid_map.delete_uid(
                uid=uid,
                store=self
            )

    @root_validator(pre=True)
    def assign_name(cls, values):
        name = values.get('name')
        if name is None:
            values['name'] = cls.__name__
        return values

    def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        raise NotImplementedError

    def create_model(
            self,
            model_type: StateModel,
            static_props: Dict[str, StaticTypes],
            dynamic_props: Dict[str, Optional[Dynamic]]) -> UID:
        raise NotImplementedError

    def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        raise NotImplementedError

    def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]) -> None:
        raise NotImplementedError

    def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        raise NotImplementedError

    def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        raise NotImplementedError

    def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str) -> List[UID]:
        raise NotImplementedError

    def create_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            inspector: RelInspector) -> None:
        raise NotImplementedError

    def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        raise NotImplementedError

    def get_model_by_backref(self, query: BackrefQuery) -> List[StateModel]:
        raise NotImplementedError

    def execute_query(
            self,
            query: Query,
            model_type: Type[StateModel],
            include_states: bool
    ) -> Dict[UID, Optional[StateModel]]:
        raise NotImplementedError

    def generate_ref(
        self,
        uid: UID,
        state_model_name: Optional[str] = None,
        state: Optional[StateModel] = None,
        guid: Optional[UUID4] = None,
        url: Optional[AnyUrl] = None
    ):
        if guid is None:
            guid = self.get_guid_record(
                uid=uid
            )
        else:
            self.link_record(uid=uid, guid=guid)

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

    def _validate_ref_uid(self, ref: Ref):
        if ref.record is None:
            raise ValueError("Can't validate uid of a ref without a record")

        model_name = ref.state_model_name
        if model_name is None:
            raise ValueError("Unspecified ref.state_model_name")

        state_model_type = get_auto_resolve_model(
            model_name=model_name,
            root_cls=StateModel
        )

        if not self.uid_exists(
            uid=ref.uid,
            model_type=state_model_type
        ):
            raise KeyError('Ref does not exist in the store')

    def _validate_ref_full(self, ref: Ref) -> Ref:
        ref = self._fetch_record_by_guid(ref)

        if ref.record is None:
            raise ValueError("Reference does not have a store record")
        if ref.record.store.uid != self.uid:
            raise ValueError(
                'Reference store record is from a different store'
            )
        self._validate_ref_uid(ref=ref)
        return ref

    def _fetch_record_by_guid(self, ref: Ref) -> Ref:
        if ref.guid is not None and self._guid_map is not None:
            uid = self._guid_map.get_uid(guid=ref.guid, store=self)
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

    def _update_relationships(
            self,
            method: Callable,
            from_uid: UID,
            from_model_type: Type[StateModel],
            field_name: str, rel: RelInspector,
            overwrite: bool = False,
            delete_orphans: bool = False):

        if overwrite is True:
            orphans = self.delete_all_relationships(
                from_uid=from_uid,
                from_model_type=from_model_type,
                rel_from_name=field_name
            )

            if delete_orphans is True:
                for orphan_uid in orphans:
                    self.delete_model(
                        uid=orphan_uid,
                        model_type=from_model_type
                    )

        to_objs_refs = []

        for to_ref in rel.to_refs:
            obj_ref = method(ref=to_ref)
            to_objs_refs.append(obj_ref)

        rel.to_refs = to_objs_refs

        self.create_relationships(
            from_uid=from_uid,
            from_model_type=from_model_type,
            inspector=rel
        )

    @to_thread
    def put(self, ref: Ref[M]) -> Ref[M]:
        """
        Creates a new record if `ref.record` is `None` or overwrites the existing record with 
        properties from `ref.state`. Only fields that are set in the `ref.state` are updated.
        
        For association and aggregation relationships, overwrite will keep the records that were
        previously related.
        
        For composition relationships, overwrite will delete previously-related
        records.

        Arguments:
            ref: Reference to the record to be created or overwritten.
        
        Returns:
            Reference to the created or overwritten record.
        """
        self._validate_method('PUT')
        ref = self._fetch_record_by_guid(ref)

        # For put inside _update_relations when relationship is a
        # reference to existing state
        if ref.state is None:
            self._validate_ref_uid(ref)
            return ref

        inspector = StateInspector.from_state(ref.state)

        if ref.record is None:
            uid = self.create_model(
                model_type=inspector.model_type,
                static_props=inspector.static_props,
                dynamic_props=inspector.dynamic_props
            )

            for field_name, rel in (
                inspector.associations | inspector.aggregations
                | inspector.compositions
            ).items():
                self._update_relationships(
                    method=partial(BaseStore.put._sync_fn, self),
                    from_uid=uid,
                    from_model_type=inspector.model_type,
                    field_name=field_name,
                    rel=rel
                )

            return self.generate_ref(
                uid=uid,
                state_model_name=ref.state_model_name,
                guid=ref.guid
            )

        else:
            ref = self._validate_ref_full(ref)
            self.overwrite_static_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.static_props
            )
            self.overwrite_dynamic_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.dynamic_props
            )
            for field_name, rel in (
                    inspector.associations | inspector.aggregations).items():
                self._update_relationships(
                    method=partial(BaseStore.put._sync_fn, self),
                    from_uid=ref.uid,
                    from_model_type=inspector.model_type,
                    field_name=field_name,
                    rel=rel,
                    overwrite=True,
                    delete_orphans=False
                )

            for field_name, rel in inspector.compositions.items():
                self._update_relationships(
                    method=partial(BaseStore.put._sync_fn, self),
                    from_uid=ref.uid,
                    from_model_type=inspector.model_type,
                    field_name=field_name,
                    rel=rel,
                    overwrite=True,
                    delete_orphans=True
                )
            return self.generate_ref(
                uid=ref.uid,
                state_model_name=ref.state_model_name,
                guid=ref.guid
            )
    @to_thread
    def patch(self, ref: Ref[M]) -> Ref[M]:
        """
        Patches properties of the existing record with the state provided in `ref.state`.

        For static properties, `patch` acts the same way as `put`. For dynamic properties,
        existing time points will be preserved and new time points, given in `ref.state`,
        will be added.

        For association relationships, `patch` will act the same way as `put`.
        
        For aggregation and composition relationships, `patch` will keep the records
        that were previously related and add new relationships from `ref.state`.

        Arguments:
            ref: Reference to the record to be patched.

        Returns:
            Reference to the patched record.
        """
        self._validate_method('PATCH')
        ref = self._validate_ref_full(ref=ref)

        if ref.state is None:
            return ref

        inspector = StateInspector.from_state(ref.state)

        if inspector.static_props != {}:
            self.overwrite_static_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.static_props
            )
        if inspector.dynamic_props != {}:
            self.extend_dynamic_props(
                uid=ref.uid,
                model_type=inspector.model_type,
                props=inspector.dynamic_props
            )

        for field_name, rel in inspector.associations.items():
            self._update_relationships(
                method=partial(BaseStore.patch._sync_fn, self),
                from_uid=ref.uid,
                from_model_type=inspector.model_type,
                field_name=field_name,
                rel=rel,
                overwrite=True,
                delete_orphans=False
            )

        for field_name, rel in (
                inspector.compositions | inspector.aggregations).items():
            self._update_relationships(
                method=partial(BaseStore.patch._sync_fn, self),
                from_uid=ref.uid,
                from_model_type=inspector.model_type,
                field_name=field_name,
                rel=rel
            )

        return self.generate_ref(
            uid=ref.uid,
            state_model_name=ref.state_model_name,
            guid=ref.guid
        )

    @to_thread
    def delete(self, ref: Ref) -> None:
        """
        Deletes the record referenced by `ref`.

        For composition relationships will also delete any related records.

        Arguments:
            ref: Reference to the record to be deleted.
        """
        self._validate_method('DELETE')

        ref = self._validate_ref_full(ref=ref)

        model_type = next(
            (
                cls for cls in all_subclasses(StateModel)
                if cls.__name__ == ref.state_model_name
            ),
            None
        )

        if model_type is None:
            raise ValueError(
                "Unknown state model name '{ref.state_model_name}'"
            )

        state = self.get_state_by_uid(
            uid=ref.uid,
            model_type=model_type
        )

        inspector = StateInspector.from_state(state)

        for field_name, rel in (
                    inspector.associations | inspector.aggregations).items():
            self.delete_all_relationships(
                from_uid=ref.uid,
                from_model_type=model_type,
                rel_from_name=field_name
            )

        for field_name, rel in inspector.compositions.items():
            orphan_models = self.delete_all_relationships(
                from_uid=ref.uid,
                from_model_type=model_type,
                rel_from_name=field_name
            )

            for orphan_uid in orphan_models:
                self.delete_model(
                    uid=orphan_uid,
                    model_type=rel.to_model
                )

        self.delete_uid_record(uid=ref.uid)

        self.delete_model(
            uid=ref.uid,
            model_type=model_type
        )
    @to_thread
    def get(self, ref: Ref[M]) -> Ref[M]:
        """
        Returns the record referenced by `ref`.

        Arguments:
            ref: Reference to the record to be retrieved.
        
        Returns:
            Reference to the retrieved record.
        """
        self._validate_method('GET')
        ref = self._validate_ref_full(ref)

        if ref.state_model_name == 'Any':
            model_type = Any
        else:
            model_type = get_auto_resolve_model(
                model_name=ref.state_model_name
            )

        return self.generate_ref(
            uid=ref.record.uid,
            state=self.get_state_by_uid(
                uid=ref.uid,
                model_type=model_type
            )
        )

    async def bulk_get(self, refs: list[Ref]) -> list[Ref]:
        self._validate_method('GET')
        return await async_map(self.get, refs)

    @to_thread
    def query(
        self,
        model_name: str,
        include_states: bool,
        query: Optional[Query] = None,
    ) -> List[Ref]:
        """
        Queries the store.

        Arguments:
            query: Query to be executed.
            model_name: Name of the model to be queried.
            include_states: Whether to include the state of the queried records.
        
        Returns:
            List of references to the records that match the query.
        """
        self._validate_method('QUERY')
        model_type = get_auto_resolve_model(
            model_name=model_name,
            root_cls=StateModel
        )

        if model_type is None:
            raise ValueError(f"Unknown model '{model_name}'")

        uids = self.execute_query(
            query=query,
            model_type=model_type,
            include_states=include_states
        )

        return [
            self.generate_ref(
                uid=uid,
                state_model_name=model_name,
                state=state
            )
            for uid, state in uids.items()
        ]

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


