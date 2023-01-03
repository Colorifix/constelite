from typing import (
    Dict, List, Optional, Literal, ClassVar, Callable
)

from pydantic import BaseModel, root_validator

from constelite.models import (
    StateModel, Ref,
    TimePoint,
    StaticTypes, RelInspector, StateInspector,
    StoreModel, StoreRecordModel, UID
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

    def ref_exists(self, ref: Ref) -> bool:
        raise NotImplementedError

    def generate_ref(self, state: Optional[StateModel], uid: UID):
        return Ref(
            record=StoreRecordModel(
                store=self,
                uid=uid
            ),
            state=state
        )

    def _validate_ref(self, ref: Ref):
        if ref.record is None:
            raise ValueError("Reference does not have a store record")
        if ref.record.name != self.name:
            raise ValueError(
                'Reference store record is from a different store'
            )
        if not self.ref_exists(ref):
            raise KeyError('Ref does not exist in the store')

    def _validate_method(self, method: StoreMethod):
        if method not in self._allowed_methods:
            raise NotImplementedError(
                f'{method} is not allowed for {self.name}'
            )

    def create_model(
            self,
            inspector: StateInspector) -> str:
        raise NotImplementedError

    def delete_model(
            self,
            uid: UID) -> None:
        raise NotImplementedError

    def overwrite_static_props(
            self,
            model_ref: Ref,
            props: Dict[str, StaticTypes]) -> None:
        raise NotImplementedError

    def overwrite_dynamic_props(
            self,
            model_ref: Ref,
            props: Dict[str, List[TimePoint]]) -> None:
        raise NotImplementedError

    def extend_dynamic_props(
            self,
            model_ref: Ref,
            props: Dict[str, List[TimePoint]]) -> None:
        raise NotImplementedError

    def delete_all_relationships(
            self,
            from_uid: Ref,
            rel_from_name: str) -> List[UID]:
        raise NotImplementedError

    def create_relationships(self, rel: RelInspector) -> None:
        raise NotImplementedError

    def get_model_by_ref(self, query: RefQuery) -> StateModel:
        raise NotImplementedError

    def get_model_by_backref(self, query: BackrefQuery) -> List[StateModel]:
        raise NotImplementedError

    def _update_relationships(
            method: Callable,
            self, from_uid: UID,
            field_name: str, rel: RelInspector,
            overwrite: bool = False,
            delete_orphans: bool = False):

        if overwrite is True:
            orphans = self.delete_all_relationships(
                from_uid=from_uid,
                rel_from_name=field_name
            )

            if delete_orphans is True:
                for orphan_uid in orphans:
                    self.delete_model(uid=orphan_uid)

        to_objs_refs = []

        for to_obj in rel.to_objs:
            obj_ref = method(to_obj)
            to_objs_refs.append(obj_ref)

        rel.to_objs = to_objs_refs

        self.create_relationships(
            from_uid=from_uid,
            rels=rel
        )

    def put(self, ref: Ref) -> Ref:
        self._validate_method('PUT')

        inspector = StateInspector.from_state(ref.state)

        if ref.record is None:
            uid = self.create_model(inspector)

            for field_name, rel in (
                inspector.associations | inspector.aggregations
                | inspector.compositions
            ).items():
                self._update_relationships(
                    method=self.put,
                    from_uid=uid,
                    field_name=field_name,
                    rel=rel
                )

            return self.generate_ref(uid=uid)

        else:
            self._validate_ref(ref)
            self.overwrite_static_props(
                record_uid=ref.uid,
                props=inspector.static_props
            )
            self.overwrite_dynamic_props(
                record_uid=ref.uid,
                props=inspector.dynamic_props
            )
            for field_name, rel in (
                    inspector.associations | inspector.aggregations).items():
                self._update_relationships(
                    method=self.put,
                    from_uid=uid,
                    field_name=field_name,
                    rel=rel,
                    overwrite=True,
                    delete_orphans=False
                )

            for field_name, rel in inspector.compositions.items():
                self._update_relationships(
                    method=self.put,
                    from_uid=uid,
                    field_name=field_name,
                    rel=rel,
                    overwrite=True,
                    delete_orphans=True
                )

            return self.generate_ref(uid=ref.uid)

    def patch(self, ref: Ref) -> Ref:
        self._validate_method('PATCH')

        self._validate_ref(ref=ref)

        inspector = StateInspector.from_state(ref.state)

        self.overwrite_static_props(
            model_ref=inspector.ref,
            props=inspector.static_props
        )

        self.extend_dynamic_props(
            model_ref=inspector.ref,
            props=inspector.dynamic_props
        )

        for field_name, rel in inspector.associations.items():
            self._update_relationships(
                method=self.patch,
                from_uid=ref.uid,
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
                field_name=field_name,
                rel=rel
            )

        return self.generate_ref(uid=ref.uid)

    def delete(self, ref: Ref) -> None:
        self._validate_method('DELETE')

        self._validate_ref(ref=ref)

        inspector = StateInspector.from_state(ref.state)

        for field_name, rel in (
                    inspector.associations | inspector.associations).items():
            self.delete_all_relationships(
                from_ref=inspector.ref,
                rel_from_name=field_name
            )

        for field_name, rel in inspector.compositions.items():
            orphan_models = self.delete_all_relationships(
                from_ref=inspector.ref,
                rel_from_name=field_name
            )

            for orphan_uid in orphan_models:
                self.delete_model(uid=orphan_uid)

        self.delete_model(uid=ref.uid)

    def get(self, ref: Ref) -> List[Ref]:
        self._validate_method('GET')
        self._validate_ref(ref)

        return self.get_model_by_uid(ref.uid)

    def query(self, query: Query) -> List[Ref]:
        return []

    def ref(self, ref: str):
        return Ref(
            ref=ref,
            store_name=self.name
        )
