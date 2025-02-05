from typing import (
    Optional, Literal, List, Set, Type, Union,  Dict, ForwardRef
)
from pydantic.v1 import BaseModel, StrictStr, StrictInt, StrictBool, StrictFloat
from pydantic.v1.fields import ModelField

from constelite.utils import resolve_forward_ref
from constelite.models.model import StateModel
from constelite.models.ref import Ref
from constelite.models.relationships import (
    Association, Aggregation, Composition, Backref
)
from constelite.models.dynamic import Dynamic
from loguru import logger
from datetime import datetime



StaticTypes = Union[
    StrictStr, StrictInt, StrictBool, StrictFloat, str, datetime,
    List[Union[StrictStr, StrictInt, StrictBool, StrictFloat, str]],
    Set[Union[StrictStr, StrictInt, StrictBool, StrictFloat, str]],
    BaseModel
]


def type_name(model: Union[Type[StateModel], ForwardRef]) -> str:
    if isinstance(model, type):
        return model.__name__
    elif isinstance(model, ForwardRef):
        return model.__forward_arg__


def type_class(model: Union[Type[StateModel], ForwardRef]) -> Type[StateModel]:
    if isinstance(model, type):
        return model
    elif isinstance(model, ForwardRef):
        logger.warning(
            f"ForwardRef in a Backref: {model}. Have you run fix_backrefs?")
        return resolve_forward_ref(model, StateModel)


class RelInspector(BaseModel):
    from_field_name: str
    to_field_name: Optional[str] = None
    to_refs: Optional[List[Ref]]
    rel_type: Literal['Association', 'Composition', 'Aggregation']
    to_model: Type[StateModel]

    @classmethod
    def from_field(
            cls,
            from_model_type: Type[StateModel],
            field: ModelField,
            to_refs: Optional[List[Ref]]):

        if to_refs is None:
            to_refs = []

        rel_type = field.type_
        rel_to_model = rel_type.model()
        if isinstance(rel_to_model, ForwardRef):
            rel_to_model = resolve_forward_ref(rel_to_model, StateModel)
            if rel_to_model is None:
                raise ValueError(
                    "Can't find a StateModel matching {rel_type.model}"
                )
        backref = next(
            (
                f for f in rel_to_model.__fields__.values()
                if (
                    isinstance(f.type_, type) and
                    issubclass(f.type_, Backref)
                    and (
                        (type_name(f.type_.model())
                         == type_name(from_model_type)) or
                        issubclass(type_class(from_model_type),
                                   type_class(f.type_.model()))
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
            rel_type=type_name(rel_type).split('[')[0],
            to_model=rel_to_model
        )

    @classmethod
    def from_backref(cls, field: ModelField, to_refs: Optional[List[Ref]]):

        if to_refs is None:
            to_refs = []

        rel_type = field.type_
        rel_to_model = rel_type.model()
        if isinstance(rel_to_model, ForwardRef):
            rel_to_model = resolve_forward_ref(rel_to_model, StateModel)
            if rel_to_model is None:
                raise ValueError(
                    "Can't find a StateModel matching {rel_type.model}"
                )
        # Do the inspection in the other direction to get the rel type
        from_field_name = field.field_info.extra['from_field']
        rel_inspector_fw = cls.from_field(
            from_model_type=rel_to_model,
            field=rel_to_model.__fields__[from_field_name],
            to_refs=[]
        )

        return cls(
            from_field_name=from_field_name,
            to_field_name=field.name,
            to_refs=to_refs,
            rel_type=rel_inspector_fw.rel_type,
            to_model=rel_to_model
        )


class StateInspector(BaseModel):
    model_type: Type[StateModel]
    static_props: Dict[str, Optional[StaticTypes]]
    dynamic_props: Dict[str, Optional[Dynamic]]

    associations: Dict[str, RelInspector]
    aggregations: Dict[str, RelInspector]
    compositions: Dict[str, RelInspector]
    backrefs: Dict[str, RelInspector]

    model: StateModel

    @classmethod
    def from_state(cls, model: StateModel):
        static_props = {}
        dynamic_props = {}
        associations = {}
        aggregations = {}
        compositions = {}
        backrefs = {}

        for field_name, field in model.__class__.__fields__.items():
            value = getattr(model, field_name)
            if value is None:
                continue
            if not isinstance(field.type_, type):
                # some typing types, e.g. Literal, Union are not classes in
                # the normal sense. Cannot run issubclass.
                # Check first and save as a static prop.
                static_props[field_name] = value
            elif issubclass(field.type_, Backref):
                backrefs[field_name] = RelInspector.from_backref(
                    field=field,
                    to_refs=value
                )
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
            # Neoflux relies on model_name field to resolve the models
            # elif field_name != 'model_name':
            else:
                static_props[field_name] = value

        return cls(
            model_type=type(model),
            static_props=static_props,
            dynamic_props=dynamic_props,
            associations=associations,
            aggregations=aggregations,
            compositions=compositions,
            backrefs=backrefs,
            model=model
        )
