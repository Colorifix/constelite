from typing import (
    Dict, List, Optional, Literal, ClassVar, Callable, Type, Any
)

from pydantic import BaseModel, root_validator

from constelite.utils import all_subclasses

from constelite.models import (
    StateModel, Ref,
    StaticTypes, Dynamic, RelInspector, StateInspector,
    StoreModel, StoreRecordModel, UID,
    get_auto_resolve_model
)


class Query(BaseModel):
    include_static: Optional[bool] = True
    include_dynamic: Optional[bool] = True
    include_associations: Optional[bool] = False
    include_compositions: Optional[bool] = True
    include_aggregations: Optional[bool] = True


class RefQuery(Query):
    ref: Ref


class BackrefQuery(RefQuery):
    class_name: str
    backref_field_name: str


StoreMethod = Literal['PUT', 'PATCH', 'GET', 'DELETE']


class BaseStore(StoreModel):
    _allowed_methods: ClassVar[
        List[StoreMethod]] = []

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

    def generate_ref(
        self,
        uid: UID,
        state_model_name: Optional[str] = None,
        state: Optional[StateModel] = None
    ):
        return Ref(
            record=StoreRecordModel(
                store=self.dict(),
                uid=uid
            ),
            state=state,
            state_model_name=state_model_name
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
        if ref.record is None:
            raise ValueError("Reference does not have a store record")
        if ref.record.store.uid != self.uid:
            raise ValueError(
                'Reference store record is from a different store'
            )
        self._validate_ref_uid(ref=ref)

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
                state_model_name=ref.state_model_name
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
                state_model_name=ref.state_model_name
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
            state_model_name=ref.state_model_name
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
            model_type = get_auto_resolve_model(model_name=ref.state_model_name)  

        return self.generate_ref(
            uid=ref.record.uid,
            state=self.get_state_by_uid(
                uid=ref.uid,
                model_type=model_type
            )
        )

    def query(self, query: Query) -> List[Ref]:
        return []
