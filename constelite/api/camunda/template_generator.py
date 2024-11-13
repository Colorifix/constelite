from typing import List, Optional, Union, Literal

from uuid import uuid4

from pydantic.v1 import BaseModel, Field

from constelite.protocol import ProtocolModel
from constelite.hook import HookModel

from .defs import (
    CONSTELITE_ENV_TEMPLATE_VARIABLE,
    RESPONSE_FIELD,
    HOOK_CALL_RESPONSE_FIELD
)

class Binding(BaseModel):
    type: str
    name: Optional[str] = None
    source: Optional[str] = None
    key: Optional[str] = None
    property: Optional[Literal["type", "retries"]] = None


class CamundaProperty(BaseModel):
    binding: Binding
    label: Optional[str] = None
    type: Optional[str] = None
    value: Optional[str] = None
    group: Optional[str] = None
    feel: Optional[str] = None


class Group(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None


class CamundaTemplate(BaseModel):
    """Camunda template object that follows (incompletely) the official
    template schema.

    Attributes:
        template_schema: Alias to `$schema`
        name:
        template_id:
        applies_to:
        properties:
        groups:
    """

    template_schema: str = Field(
        default=(
            "https://unpkg.com/@camunda/zeebe-element-templates-json-schema"
            "@0.9.0/resources/schema.json"
        ),
        alias="$schema",
    )

    name: str
    template_id: Optional[str] = Field(
        alias="id", default_factory=lambda: str(uuid4())
    )
    applies_to: Optional[List[str]] = Field(
        alias="appliesTo", default=["bpmn:ServiceTask"]
    )
    properties: Optional[List[CamundaProperty]]
    groups: List[Group]


def generate_input_props(model: Union[ProtocolModel, HookModel]) -> List[CamundaProperty]:
    props = []
    for field_name, field in model.fn_model.__fields__.items():
        if not field_name.startswith("_"):
            prop = CamundaProperty(
                label=field_name,
                binding=Binding(type="zeebe:input", name=field_name),
                group="input",
                feel="optional",
                type="String",
            )
            props.append(prop)

    return props


def generate_inbound_config_props(hook_model: HookModel) -> List[CamundaProperty]:
    correlation_key_prop = CamundaProperty(
        label="Correlation key",
        binding=Binding(type="zeebe:input", name="correlation_key"),
        group="config",
        feel="optional",
        type="String",
    )

    message_name_prop = CamundaProperty(
        label="Message name",
        binding=Binding(type="zeebe:input", name="message_name"),
        group="config",
        feel="optional",
        type="String",
    )

    return [correlation_key_prop, message_name_prop]


def generate_output_prop(model: Union[ProtocolModel, HookModel]) -> Optional[CamundaProperty]:
    if model.ret_model is not None:
        prop = CamundaProperty(
            label="Result variable",
            binding=Binding(type="zeebe:output", source=f"={RESPONSE_FIELD}"),
            type="String",
            group="output",
        )
        return prop

def generate_template(model: Union[ProtocolModel, HookModel]) -> CamundaTemplate:
    props = generate_input_props(model)


    if isinstance(model, ProtocolModel):
        output_prop = generate_output_prop(model)
        
        if output_prop is not None:
            props.append(output_prop)
    else:
        props.extend(generate_inbound_config_props(model))

        output_prop = CamundaProperty(
            label="Result variable",
            binding=Binding(type="zeebe:output", source=f"={HOOK_CALL_RESPONSE_FIELD}"),
            type="String",
            group="output",
        )

        props.append(output_prop)
    
    task_type_prop = CamundaProperty(
        value=f'= {CONSTELITE_ENV_TEMPLATE_VARIABLE}+ "-{model.slug}"',
        type="Hidden",
        binding=Binding(type="zeebe:taskDefinition", property="type")
    )
    props.append(task_type_prop)

    groups = [
        Group(id="input", label="Input"),
        Group(id="output", label="Output"),
        Group(id="config", label="Configuration"),
    ]

    template = CamundaTemplate(
        name=model.name, properties=props, groups=groups
    )

    return template