from typing import (
    Union, Dict, List, TypeVar, Type, Optional, Literal, ForwardRef, ClassVar
)

from pydantic import BaseModel, root_validator
from pydantic.fields import ModelField

from constelite.models import (
    Model, ConsteliteBaseModel, Ref,
    TimePoint, Dynamic, Association, Aggregation, Composition, Relationship,
    Backref
)


StaticTypes = Union[int, str, bool, BaseModel, float]


M = TypeVar('Model')


def type_name(model: Union[Type[Model], ForwardRef]):
    if isinstance(model, type):
        return model.__name__
    elif isinstance(model, ForwardRef):
        return model.__forward_arg__


class RelInspector(BaseModel):
    from_field_name: str
    to_field: Optional[str] = ...
    to_objs: Optional[List[M]]
    rel_type: Literal['Association', 'Composition', 'Aggregation']

    @classmethod
    def from_field(
            cls,
            from_model_type: Type[Model],
            field: ModelField,
            values: Optional[List[M]]):

        rel_type = field.type_
        rel_to_model = rel_type.model

        backref = next(
            (
                f for f in rel_to_model.__fields__.values()
                if (
                    issubclass(f.type_, Relationship)
                    and (
                        type_name(f.type_.model)
                        == type_name(from_model_type)
                    )
                )
            ),
            None
        )

        return cls(
            from_field_name=field.name,
            to_field=backref.name,
            to_objs=values,
            rel_type=type_name(rel_type).split('[')[0]
        )


class ModelInspector(BaseModel):
    model_type: Type[Model]
    static_props: Dict[str, Optional[StaticTypes]]
    dynamic_props: Dict[str, Optional[Dynamic]]

    associations: Dict[str, RelInspector]
    aggregations: Dict[str, RelInspector]
    compositions: Dict[str, RelInspector]

    ref: Optional[Ref]
    model: Model

    @classmethod
    def from_model(cls, model: Model):
        static_props = {}
        dynamic_props = {}
        associations = {}
        aggregations = {}
        compositions = {}

        ref = None

        for field_name, field in model.__class__.__fields__.items():
            value = getattr(model, field_name)
            if issubclass(field.type_, Backref):
                pass
            elif issubclass(field.type_, Dynamic):
                value = getattr(model, field_name)
                dynamic_props[field_name] = value

            elif issubclass(field.type_, Association):
                associations[field_name] = RelInspector.from_field(
                    from_model_type=type(model),
                    field=field,
                    values=value
                )
            elif issubclass(field.type_, Aggregation):
                aggregations[field_name] = RelInspector.from_field(
                    from_model_type=type(model),
                    field=field,
                    values=value
                )
            elif issubclass(field.type_, Composition):
                compositions[field_name] = RelInspector.from_field(
                    from_model_type=type(model),
                    field=field,
                    values=value
                )
            elif field_name == 'ref':
                ref = value
            else:
                static_props[field_name] = value

        return cls(
            model_type=type(model),
            static_props=static_props,
            dynamic_props=dynamic_props,
            associations=associations,
            aggregations=aggregations,
            compositions=compositions,
            ref=ref,
            model=model
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


class BaseStore(ConsteliteBaseModel):
    _allowed_methods: ClassVar[
        List[StoreMethod]] = []
    name: str

    @root_validator(pre=True)
    def assign_name(cls, values):
        name = values.get('name')
        if name is None:
            values['name'] = cls.__name__
        return values

    def ref_exists(self, ref: Ref) -> bool:
        raise NotImplementedError

    def _validate_ref(self, ref: Ref):
        if ref.store_name != self.name:
            raise ValueError('Ref does not match the store')
        if not self.ref_exists(ref):
            raise KeyError('Ref does not exist in the store')

    def _validate_method(self, method: StoreMethod):
        if method not in self._allowed_methods:
            raise NotImplementedError(
                f'{method} is not allowed for {self.name}'
            )

    def create_model(
            self,
            inspector: ModelInspector) -> Model:
        raise NotImplementedError

    def delete_model(
            self,
            ref: Ref) -> None:
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
            from_ref: Ref,
            rel_from_name: str,
            delete_to_nodes: bool) -> None:
        raise NotImplementedError

    def create_relationships(self, rel: RelInspector) -> None:
        raise NotImplementedError

    def get_model_by_ref(self, query: RefQuery) -> Model:
        raise NotImplementedError

    def get_model_by_backref(self, query: BackrefQuery) -> List[Model]:
        raise NotImplementedError

    def put(self, model: Model) -> Model:
        self._validate_method('PUT')

        inspector = ModelInspector.from_model(model)
        new = inspector.ref is None

        ret_model = model

        if new:
            ret_model = self.create_model(inspector)

            for field_name, rel in (
                inspector.associations | inspector.aggregations
                | inspector.compositions
            ).items():

                to_objs_ref_only = []

                for to_obj in rel.to_objs:
                    ref = self.put(to_obj)
                    to_objs_ref_only.append(ref)

                rel.to_objs = to_objs_ref_only

                self.create_relationships(
                    from_ref=ret_model.ref,
                    rels=rel
                )

        else:
            self._validate_ref(inspector.ref)
            self.overwrite_static_props(
                model_ref=inspector.ref,
                props=inspector.static_props
            )
            self.overwrite_dynamic_props(
                model_ref=inspector.ref,
                props=inspector.dynamic_props
            )
            for field_name, rel in (
                    inspector.associations | inspector.aggregations).items():
                self.delete_all_relationships(
                    from_ref=inspector.ref,
                    rel_from_name=field_name
                )

                to_objs_ref_only = []

                for to_obj in rel.to_objs:
                    ref = self.put(to_obj)
                    to_objs_ref_only.append(ref)

                rel.to_objs = to_objs_ref_only
                self.create_relationships(
                    from_ref=inspector.ref,
                    rels=rel
                )

            for field_name, rel in inspector.compositions.items():
                orphan_models = self.delete_all_relationships(
                    from_ref=inspector.ref,
                    rel_from_name=field_name
                )

                for orphan in orphan_models:
                    self.delete(orphan)

                to_objs_ref_only = []

                for to_obj in rel.to_objs:
                    ref = self.put(to_obj)
                    to_objs_ref_only.append(ref)

                rel.to_objs = to_objs_ref_only
                self.create_relationships(
                    from_ref=inspector.ref,
                    rels=rel
                )

        return ret_model

    def patch(self, model: Model) -> Model:
        self._validate_method('PATCH')

        if model.ref is None:
            raise ValueError('Passed model does not have a reference')

        self._validate_ref(ref=model.ref)

        inspector = ModelInspector.from_model(model)

        self.overwrite_static_props(
            model_ref=inspector.ref,
            props=inspector.static_props
        )

        self.extend_dynamic_props(
            model_ref=inspector.ref,
            props=inspector.dynamic_props
        )

        for field_name, rel in inspector.associations.items():
            self.delete_all_relationships(
                from_ref=inspector.ref,
                rel_from_name=field_name
            )

            to_objs_ref_only = []

            for to_obj in rel.to_objs:
                ref = self.patch(to_obj)
                to_objs_ref_only.append(ref)

            rel.to_objs = to_objs_ref_only
            self.create_relationships(
                from_ref=inspector.ref,
                rels=rel
            )

        for field_name, rel in (
                inspector.compositions | inspector.aggregations).items():
            to_objs_ref_only = []

            for to_obj in rel.to_objs:
                ref = self.patch(to_obj)
                to_objs_ref_only.append(ref)

            rel.to_objs = to_objs_ref_only
            self.create_relationships(
                from_ref=inspector.ref,
                rels=rel
            )

        return model

    def delete(self, model: Model) -> None:
        self._validate_method('DELETE')

        if model.ref is None:
            raise ValueError('Passed model does not have a reference')

        self._validate_ref(ref=model.ref)

        inspector = ModelInspector.from_model(model)

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

            for orphan in orphan_models:
                self.delete(orphan)

        self.delete_model(inspector.ref)

    def get(self, query: Query) -> List[Model]:
        self._validate_method('GET')

        if isinstance(query, RefQuery):
            return self.get_model_by_ref(query)
        elif isinstance(query, BackrefQuery):
            return self.get_model_by_backref(query)
        else:
            raise ValueError('Unsupported query type')

    def ref(self, ref: str):
        return Ref(
            ref=ref,
            store_name=self.name
        )
