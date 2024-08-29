# Writing a converter protocol


## What is a converter protocol?

Converter protocol (or Converter) is a special type of protocol designed to simplify conversions of one type of asset to another, following the process-asset model.

Scheduling an asset to be processed by one of the Colorifix services is a common operation we deal with. Converter provides a standard way of performing this task, so you can focus on the conversion logic and don't worry about the rest.

Converters can be handy to perform three kind of things:

1. Create a new request with or without inputs.
2. Add a new input-output pair to an existing request.
3. Generate outputs for an existing requests and inputs defined elsewhere (e.g. in Notion)

## Interface

Each converter protocol takes exactly three arguments:

`store: BaseStore`

:   A store where the output assets will be created

`r_request: Ref[IORequest]`

:   Request to which the input and output assets will be associated to. Can be either an existing request (with record specified) or a record-less reference. In the later case, a new request will be created in the provided store with the state given in the `r_request`. 

`inputs: Optional[List[InputType]]`

:   A list of inputs to convert, where `InputType` is a converter-specific model of inputs derived from `RequestInput`.

!!! note
    If no inputs are provided and `r_request` has a record (i.e. already exists), converter will use inputs from the existing request.

    If no inputs are provided and `r_request` has no record, converter will create a new
    request using data from `r_request.state`. 

Each converter must have a

`convert(self, api, store: BaseStore, input: InputType) -> OutputType`

method defined that encapsulates the conversion logic of one input to one output, where `OutputType` is a converter-specific output model derived from `RequestOutput`.

Optionally, a converter can define a

`async def validate_input(self, api, store: BaseStore, input: InputType) -> InputType`

method that perform a validation on one given input. It must return an input back. The returned input will be used for conversion. This gives you an opportunity to fetch states of input references before passing the input to the converter.

## How does it work?

When converter is called, it tries to validate each given input using the `validate_input` method. If validation succeeds, converter will generate a list of outputs by processing each input through the `convert` method. Finally, it will associate both inputs and outputs to the provided request. 

The output of the converter is a dictionary containing two fields:

`outputs: List[OutputType]`

:    Converted outputs

`r_request: Ref[Request]`

:    Reference to the request to which inputs and outputs were assigned to.

## Example

```python
from colorifix_alpha.protocols.requests.io import ConverterProtocol
from colorifix_alpha.models import RequestInput, RequestOutput, IO

from constelite.models import Association

class AdoptCatInput(RequestInput):
    owner: Association[Owner]
    name: str #Name for an adopted cat

class AdoptCatOutput(RequestInput):
    cat: Association[Cat]

class AdoptCatIO(IO[AdoptCatInput, AdoptCatOutput]):
    pass

class AdoptCat(ConverterProtocol[AdoptCatIO]):
    async def convert(self, api, store: BaseStore, input: AdoptCatInput) -> AdoptCatOutput:
        r_cat = await store.put(ref(
            Cat(
                name=input.name,
                r_owner=input.owner
            )
        ))

        return AdoptCatOutput(
            cat = [r_cat]
        )
```

Here we crate a simple converter that helps us to schedule an adoption of a cat by a new owner. We could also add input validation to check whether a potential owner has a reference. We don't want to let unverified people take care of pets.

```python
class AdoptCat(ConverterProtocol[AdoptCatInput, AdoptCatOutput]):
    ...

    async def validate_input(self, api, store: BaseStore, input: AdoptCatInput) -> AdoptCatInput:
        await api.get_state(input.r_owner)
        
        assert input.r_owner.has_reference, "Owner does not have a reference"

        return input
```

## IO and IORequest

Requests are modeled using `IORequest` state model.

```python
class IORequest(StateModel):
    name: Optional[str]
    status: Optional[Status]
    to_activity: Optional[Association[Service]]
    for_workflow_instance: Optional[Association[IORequest]]
    request_type: Optional[Set[RequestType]]

    ios: Optional[Aggregation[IO]] = None
```

Each request is an aggregation of one or more IOs. Each IO represents a single execution of a process and stores information about inputs passed to the process and outputs resulted from the execution of the process.

```python
InputType = TypeVar("InputType", bound=RequestInput)
OutputType = TypeVar("OutputType", bound=RequestOutput)


class IO(StateModel, Generic[InputType, OutputType], GenericModel):
    input: Optional[InputType]
    output: Optional[OutputType]
```

## Notion handlers

In Notion, We store all IOs in the [Unified IO table](https://www.notion.so/colorifix/6480f7eb78c34af8806333e1f0bf17e0?v=168488eec65e475ab8eb0eaf23597207).

Note that although we can have many IO state models in constelite, they all end up in the same table.

When you create a new IO class for you converter protocol, you must also add an IOHandler to allow Notion store to convert between the rows in the Unified IO table to your new IO state model.

Here how an IOHandler would look like for the example above:

```python
from typing import  Optional

from pydantic.v1 import Field

from python_notion_api.models.values import (
    RelationPropertyValue,
    RichTextPropertyValue
)

from .io import IOHandler
from colorifix_alpha.protocols.requests.converters.adopt_cat import AdoptCatInput, AdoptCatOutput

class AdoptCatIOHandler(IOHandler):
    _input_model = AdoptCatInput
    _output_model = AdoptCatOutput

    input_owner: Optional[RelationPropertyValue] = Field(
        alias="Cat's owner",
        json_schema_extra={
            "constelite_name": "owner"
        }
    )

    cats_name: Optional[RichTextPropertyValue] = Field(
        alias="Cat's name",
        json_schema_extra={
            "constelite_name": "name"
        }
    )

    output_cat: Optional[RelationPropertyValue] = Field(
        alias="Adopted cat",
        json_schema_extra={
            "constelite_name": "cat"
        }
    )
```
Let's break it down:

`_input_model` and `_output_model` tell IOHandler which input and output models to use for conversion of the Notion rows.

!!! warning
    Don't use the same field names for both input and output models. E.g. if we included `name` field in the `AdoptCatOutput`, the handler will have difficulty choosing whether to associate Notion property with `AdoptCatInput` or `AdoptCatOutput`

Each field in the IOHandler represents a Notion property with aliases specifying either name or id of the property.

`constelite_name` is a name of the corresponding field either in the `_input_model` or `_output_model`.

Last step before it all can work is to associate your IO state model with the IOHandler. For that, you need to add mapping in the `api.py`.

```python
notion_store = NotionStore(
    model_handlers={
        ...
        AdoptCatIO: AdoptCatIOHandler   
    }
)
```