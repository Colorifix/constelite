# Adding new store

Stores are abstraction ove data repositories. Data repositories can be anything that allows to read, write, modify, query and delete structured data. For example, it can be a database, a file or a in-memory storage.

To add a support for a new type of store you need to create a new store class and implement abstract methods.

```python
from constelite.store import AsyncBaseStore

class MyStore(AsyncBaseStore):
    async def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        raise NotImplementedError

    async def create_model(
            self,
            model_type: Type[StateModel],
            static_props: Dict[str, StaticTypes],
            dynamic_props: Dict[str, Optional[Dynamic]]) -> UID:
        raise NotImplementedError

    async def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        raise NotImplementedError

    async def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]) -> None:
        raise NotImplementedError

    async def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        raise NotImplementedError

    async def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        raise NotImplementedError

    async def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str) -> List[UID]:
        raise NotImplementedError

    async def create_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            inspector: RelInspector) -> None:
        raise NotImplementedError

    async def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        raise NotImplementedError
```

Note, that you don't have to re-implement `put`, `patch`, `get`, `delete` and `query` methods. They are already implemented in the `AsyncBaseStore`.

Also note, that constelite is moving towards being 100% async so we recommend you implement your store from `AsyncBaseStore`.

The `AsyncBaseStore` is derived from `BaseModel`, so you can add any extra fields required for store configuration.

Let's look at each function separately.

## UID exisits

This is a simple function that must return `True` if the store has a record under the given `uid` or `False` otherwise.

## Create model

This function is responsible for creating a new record in the store and it must return UID of the record that would point to the new record. This will be called when user wants to create a new record in the store.

`static_props` is a key-value dictionary for static properties. Static properties are simple properties of types like `int`, `str`, `list`, `StateModel`, `bool`, etc.

`dynamic_props` are special types of properties that deal with storing time-series. In practice, we use them rarely. So if you don't want support dynamic properties, you can ignore them. If you do, check out implementation of the Neoflux store.

## Delete model

This one must delete the record with the given uid from the store. Constelite will assume that record will no longer be accessible and `uid_exists` will return `False` after this operation.

## Overwrite static props

This function must overwrite all properties of the record with those supplied in `props`. If property is not present in the `props`, its value must remain unchanged.

## Overwrite dynamic props

Same as for static props.

## Delete all relationships

This function must delete all relationships from the record with the UID supplied in `from_uid` to all the records associated through the relationship under attribute supplied in `rel_from_name`. For example, if we are asked to delete all relationships from `Cat` record with `rel_from_name = "carer"`, the function must delete all relationships between the given cat and all humans that are associated with a cat through the "carer" attribute.

```python

class Cat(StateModel):
    name: str
    carer: Association[Human]
```

## Create relationships

This function must create relationships between a record with the UID supplied in `from_uid` following the instructions in the `inspector`. `RelInspector` has the following model:

```python
class RelInspector(BaseModel):
    from_field_name: str
    to_field_name: Optional[str] = None
    to_refs: Optional[List[Ref]]
    rel_type: Literal['Association', 'Composition', 'Aggregation']
    to_model: Type[StateModel]
```

`from_field_name` tells the name of the attribute that corresponds to the relationship. If we are creating new relationships for a cat's carer, this will be equal "carer".

`to_field_name` will be empty as we don't have a `Backref` from `Human` to `Cat`. 

`to_refs` will contain a list of references to the humans we want to associate our cat with. Note, that you don't need to worry about the state models of the related humans. You can assume that they already exist in the store and each given ref will have a valid UID.

`rel_type` will correspond to the type of relationship we are dealing with. In our car case, it will be "Association".

`to_model` will be a type of model we are relating to. In our case, `Human`

## Get state by uid

This function must return a state model for the record with given UID. You can assume that the record with the given UID exists.