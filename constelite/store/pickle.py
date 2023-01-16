from typing import List, Dict, Optional, Type

import os

import pickle

from uuid import uuid4

from pydantic import Field

from constelite.models import (
    StateModel, UID, TimePoint, Dynamic,
    StaticTypes, RelInspector, resolve_model
)

from constelite.store import (
    BaseStore
)


class PickleStore(BaseStore):
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE"]
    path: Optional[str] = Field(exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)

    def uid_exists(self, uid: UID) -> bool:
        path = os.path.join(self.path, uid)
        return os.path.exists(path)

    def get_model_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        if not self.uid_exists(uid):
            raise ValueError(f"Model with reference '{uid}' cannon be found")
        else:
            path = os.path.join(self.path, uid)
            with open(path, 'rb') as f:
                return resolve_model(
                    values=pickle.load(f)
                )

    def store(self, uid: UID, model: StateModel) -> UID:
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

    def create_model(
            self,
            model_type: StateModel,
            static_props: Dict[str, StaticTypes],
            dynamic_props: Dict[str, Optional[Dynamic]]) -> UID:
        model = model_type(
            **(static_props | dynamic_props)
        )
        uid = str(uuid4())
        uid = self.store(uid=uid, model=model)
        return uid

    def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        if self.uid_exists(uid):
            path = os.path.join(self.path, uid)
            os.remove(path)

    def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]) -> None:

        model = self.get_model_by_uid(
            uid=uid,
            model_type=model_type
        )
        data = model.dict()
        data.update(props)

        new_model = model.__class__(
            **data
        )

        self.store(uid=uid, model=new_model)

    def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, List[TimePoint]]) -> None:
        model = self.get_model_by_uid(
            uid=uid,
            model_type=model_type
        )
        data = model.dict()
        data.update(props)

        new_model = model.__class__(
            **data
        )
        self.store(uid=uid, model=new_model)

    def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        model = self.get_model_by_uid(
            uid=uid,
            model_type=model_type
        )

        for prop_name, prop in props.items():
            points = getattr(
                model,
                prop_name,
                Dynamic[prop._point_type](points=[])
            ).points

            points.extend(prop.points)
            setattr(
                model,
                prop_name,
                Dynamic[prop._point_type](points=points)
            )
        self.store(uid=uid, model=model)

    def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str,
            ) -> List[UID]:

        model = self.get_model_by_uid(
            uid=from_uid,
            model_type=from_model_type
        )

        orphan_refs = getattr(model, rel_from_name, [])
        setattr(model, rel_from_name, [])

        self.store(uid=from_uid, model=model)

        return [orphan_ref.record.uid for orphan_ref in orphan_refs]

    def create_relationships(self, from_uid: UID, inspector: RelInspector) -> None:
        from_model = self.get_model_by_uid(
            uid=from_uid,
            model_type=inspector.to_model
        )

        to_refs = getattr(from_model, inspector.from_field_name, [])
        if to_refs is None:
            to_refs = []

        new_to_refs = (
            inspector.to_refs
            if inspector.to_refs is not None
            else []
        )

        for to_ref in new_to_refs:
            to_uid = to_ref.uid
            to_refs.append(to_ref)
            if inspector.to_field_name is not None:
                to_model = self.get_model_by_uid(uid=to_uid)
                backref_list = getattr(to_model, inspector.to_field_name)
                from_ref = self.generate_ref(uid=from_uid)
                if backref_list is None:
                    backref_list = [from_ref]
                else:
                    backref_list.append(from_ref)
                setattr(to_model, inspector.to_field_name, backref_list)
                self.store(uid=to_uid, model=to_model)
        setattr(from_model, inspector.from_field_name, to_refs)
        self.store(uid=from_uid, model=from_model)

