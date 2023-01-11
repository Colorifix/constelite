from typing import (
    Optional, Literal, List, Type, Union, TypeVar, Dict, ForwardRef
)
from pydantic import BaseModel
from pydantic.fields import ModelField

from constelite.models.model import StateModel
from constelite.models.ref import Ref
from constelite.models.relationships import (
    Relationship, Association, Aggregation, Composition, Backref
)
from constelite.models.dynamic import Dynamic

StaticTypes = Union[int, str, bool, BaseModel, float]


M = TypeVar('Model')


def type_name(model: Union[Type[StateModel], ForwardRef]) -> str:
    if isinstance(model, type):
        return model.__name__
    elif isinstance(model, ForwardRef):
        return model.__forward_arg__


class RelInspector(BaseModel):
    from_field_name: str
    to_field_name: Optional[str] = ...
    to_refs: Optional[List[Ref]]
    rel_type: Literal['Association', 'Composition', 'Aggregation']

    @classmethod
    def from_field(
            cls,
            from_model_type: Type[StateModel],
            field: ModelField,
            to_refs: Optional[List[Ref]]):

        if to_refs is None:
            to_refs = []
        rel_type = field.type_
        rel_to_model = rel_type.model
        backref = next(
            (
                f for f in rel_to_model.__fields__.values()
                if (
                    issubclass(f.type_, Backref)
                    and (
                        type_name(f.type_.model)
                        == type_name(from_model_type)
                    )
                    and (
                        f.field_info.extra.get('from_field', None)
                        == field.name
                    )
                )
            ),
            None
        )

        return cls(
            from_field_name=field.name,
            to_field_name=backref.name if backref is not None else None,
            to_refs=to_refs,
            rel_type=type_name(rel_type).split('[')[0]
        )


class StateInspector(BaseModel):
    model_type: Type[StateModel]
    static_props: Dict[str, Optional[StaticTypes]]
    dynamic_props: Dict[str, Optional[Dynamic]]

    associations: Dict[str, RelInspector]
    aggregations: Dict[str, RelInspector]
    compositions: Dict[str, RelInspector]

    model: StateModel

    @classmethod
    def from_state(cls, model: StateModel):
        static_props = {}
        dynamic_props = {}
        associations = {}
        aggregations = {}
        compositions = {}

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
                    to_refs=value
                )
            elif issubclass(field.type_, Aggregation):
                aggregations[field_name] = RelInspector.from_field(
                    from_model_type=type(model),
                    field=field,
                    to_refs=value
                )
            elif issubclass(field.type_, Composition):
                compositions[field_name] = RelInspector.from_field(
                    from_model_type=type(model),
                    field=field,
                    to_refs=value
                )
            else:
                static_props[field_name] = value

        return cls(
            model_type=type(model),
            static_props=static_props,
            dynamic_props=dynamic_props,
            associations=associations,
            aggregations=aggregations,
            compositions=compositions,
            model=model
        )
