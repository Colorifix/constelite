from typing import List, Dict

import os

import pickle

from uuid import uuid4

from constelite.models.model import Ref, Model
from constelite.models.dynamic import TimePoint, Dynamic
from constelite.store import (
    BaseStore, StaticTypes, ModelInspector, RelInspector,
    RefQuery, BackrefQuery
)


class PickleStore(BaseStore):
    path: str

    def __post_init_post_parse__(self):
        if not os.path.isdir(self.path):
            os.makedirs(self.path)

    def new_ref(self) -> Ref:
        ref = None
        while ref is None or self.ref_exists(ref):
            ref = Ref(ref=str(uuid4()), store_name=self.ref)

        return ref

    def ref_exists(self, ref: Ref) -> bool:
        path = os.path.join(self.path, ref.ref)
        return os.path.exists(path)

    def load(self, ref: Ref) -> "Model":
        if not self.ref_exists(ref):
            raise ValueError(f"Model with reference '{ref}' cannon be found")
        else:
            path = os.path.join(self.path, ref.ref)
            with open(path, 'rb') as f:
                return pickle.load(f)

    def store(self, model):
        path = os.path.join(self.path, model.ref.ref)

        exception = None

        with open(path, 'wb') as f:
            try:
                pickle.dump(model, f)
            except Exception as e:
                exception = e

        if exception is not None:
            os.remove(path)
            raise exception

    def create_model(
            self,
            inspector: ModelInspector) -> Model:

        ref = self.new_ref()

        model = inspector.model_type(
            ref=ref,
            **(inspector.static_props | inspector.dynamic_props)
        )
        self.store(model)
        return model

    def delete_model(
            self,
            ref: Ref) -> None:
        if self.ref_exists(ref):
            path = os.path.join(self.path, ref.ref)
            os.remove(path)

    def overwrite_static_props(
            self,
            model_ref: Ref,
            props: Dict[str, StaticTypes]) -> None:

        model = self.load(ref=model_ref.ref)
        data = model.dict()
        data.update(props)

        new_model = self.model.__class__(
            **data
        )

        self.store(new_model)

    def overwrite_dynamic_props(
            self,
            model_ref: Ref,
            props: Dict[str, List[TimePoint]]) -> None:

        model = self.load(ref=model_ref.ref)
        data = model.dict()
        data.update(props)

        new_model = self.model.__class__(
            **data
        )
        self.store(new_model)

    def extend_dynamic_props(
            self,
            model_ref: Ref,
            props: Dict[str, List[TimePoint]]) -> None:
        model = self.load(ref=model_ref)
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
        self.store(model)

    def delete_all_relationships(
            self,
            from_ref: Ref,
            rel_from_name: str,
            delete_to_nodes: bool) -> List['Model']:

        model = self.load(ref=from_ref.ref)

        orphans = getattr(model, rel_from_name, [])
        setattr(model, rel_from_name, [])

        self.store(model)

        return orphans

    def create_relationships(self, from_ref: Ref, rels: RelInspector) -> None:
        model = self.load(ref=from_ref.ref)

        to_objs = getattr(model, rels.from_field_name, [])
        if to_objs is None:
            to_objs = []

        new_to_nodes = rels.to_objs if rels.to_objs is not None else []

        for to_node in new_to_nodes:
            to_objs.append(to_node)
            if rels.to_field is not None:
                to_node_store = self.models[to_node.ref.ref]
                backref_list = getattr(to_node_store, rels.to_field)
                if backref_list is None:
                    backref_list = [model]
                else:
                    backref_list.append(model)
                setattr(to_node_store, rels.to_field, backref_list)
                self.models[to_node.ref.ref] = to_node_store
        setattr(model, rels.from_field_name, to_objs)
        self.store(model)

    def get_model_by_ref(self, query: RefQuery) -> Model:
        if self.ref_exists(query.ref):
            return self.load(ref=query.ref)

    def get_model_by_backref(self, query: BackrefQuery) -> List[Model]:
        return None
