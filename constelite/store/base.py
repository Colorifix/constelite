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

from pydantic import BaseModel, root_validator, PrivateAttr, UUID4

from constelite.utils import all_subclasses

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


StoreMethod = Literal['PUT', 'PATCH', 'GET', 'DELETE', 'QUERY']


class BaseStore(StoreModel):
    _allowed_methods: ClassVar[
        List[StoreMethod]] = []

    _guid_map: Optional[GUIDMap] = PrivateAttr(default=None)

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
        guid: Optional[UUID4] = None
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
                uid=uid
            ),
            state=state,
            state_model_name=state_model_name,
            guid=guid
        )

    def _validate_ref_uid(self, ref: Ref):
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

    def _validate_ref_full(self, ref: Ref):
        self._fetch_record_by_guid(ref)

        if ref.record is None:
            raise ValueError("Reference does not have a store record")
        if ref.record.store.uid != self.uid:
            raise ValueError(
                'Reference store record is from a different store'
            )
        self._validate_ref_uid(ref=ref)

    def _fetch_record_by_guid(self, ref: Ref):
        if ref.guid is not None and self._guid_map is not None:
            uid = self._guid_map.get_uid(guid=ref.guid, store=self)

            if uid is not None:
                ref.record = StoreRecordModel(
                    store=self,
                    uid=uid
                )
            else:
                ref.record = None

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

    def put(self, ref: Ref) -> Ref:
        self._validate_method('PUT')
        # For put inside _update_relations when relationship is a
        # reference to existing state
        if ref.state is None:
            self._validate_ref_uid(ref)
            return ref

        inspector = StateInspector.from_state(ref.state)

        self._fetch_record_by_guid(ref)

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
                    method=self.put,
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
            self._validate_ref_full(ref)
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
                    method=self.put,
                    from_uid=ref.uid,
                    from_model_type=inspector.model_type,
                    field_name=field_name,
                    rel=rel,
                    overwrite=True,
                    delete_orphans=False
                )

            for field_name, rel in inspector.compositions.items():
                self._update_relationships(
                    method=self.put,
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

    def patch(self, ref: Ref) -> Ref:
        self._validate_method('PATCH')
        self._validate_ref_full(ref=ref)

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
                method=self.patch,
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
                method=self.patch,
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

    def delete(self, ref: Ref) -> None:
        self._validate_method('DELETE')

        self._validate_ref_full(ref=ref)

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

    def get(self, ref: Ref) -> Ref:
        self._validate_method('GET')
        self._validate_ref_full(ref)

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

    def query(
        self,
        query: Query,
        model_name: str,
        include_states: bool
    ) -> List[Ref]:
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
        # Experimental
        #
        # if include_states:
        #     for field_name, field in model_type.__fields__.items():
        #         if issubclass(field.type_, Relationship):
        #             for uid, state in uids.items():
        #                 rels = getattr(state, field_name)
        #                 for ref in rels:
        #                     ref.state = self.get(ref=ref)

        return [
            self.generate_ref(
                uid=uid,
                state_model_name=model_name,
                state=state
            )
            for uid, state in uids.items()
        ]
