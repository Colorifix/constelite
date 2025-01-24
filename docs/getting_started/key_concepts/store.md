## Intro

Think of a store as a constelite wrapper around an API of a data provider.

Every store is represented by a [BaseStore][constelite.store.BaseStore] object. If we want to connect to a data provider through constelite we need to create a store of a corresponding type.

For example, we have MemoryStore, which stores records in memory, or NeofluxStore, which stores records in external Neo4j and InfluxDB databases.

!!! note
    If you want to reach another kind of data provider, you need to write a new store class.

## Why can't we use existing libraries to talk to data provider?

You are right, there are plenty of libraries to talk with Neo4j. And we use them inside constelite store classes.

Stores are just wrappers with a standard API so that constelite and constelite users don't need to worry about particular ways of reading and writing data associated with a particular data provider. All specific logic is implemented inside stores once and  is then reused through a standard interface.

For example, to save a new record to a store, all you need to do is

```py
store: Store

r_cat = ref(
    Cat(
        name="Snowball"
    )
)

store.put(ref=r_cat)
```

Where the record is created will depend on the `store` object.

## Store methods

Each store implements a set of standard methods, which are:

### `get(ref:Ref[M]) -> Ref[M]`
::: constelite.store.BaseStore.get
    options:
          show_docstring_parameters: false
          show_docstring_returns: false
          show_source: false
          heading_level: 0
### `put(ref: Ref[M]) -> Ref[M]`
::: constelite.store.BaseStore.put
    options:
          show_docstring_parameters: false
          show_docstring_returns: false
          show_source: false
          heading_level: 0
### `patch(ref: Ref[M]) -> Ref[M]`
::: constelite.store.BaseStore.patch
    options:
          show_docstring_parameters: false
          show_docstring_returns: false
          show_source: false
          heading_level: 0
### `delete(ref:Ref) -> None`
::: constelite.store.BaseStore.delete
    options:
          show_docstring_parameters: false
          show_docstring_returns: false
          show_source: false
          heading_level: 0
### `query(query: Query, model_type: Type[StateModel], include_states: bool) -> List[Ref[M]]`
::: constelite.store.BaseStore.query
    options:
          show_docstring_parameters: false
          show_docstring_returns: false
          show_source: false
          heading_level: 0
### `graphql(self, query: GraphQLQuery) -> Dict[str, Any]:`
::: constelite.store.BaseStore.graphql
    options:
          show_docstring_parameters: false
          show_docstring_returns: false
          show_source: false
          heading_level: 0
### `graphql_models(self, query: GraphQLModelQuery) -> List[Ref]:`
::: constelite.store.BaseStore.graphql_models
    options:
          show_docstring_parameters: false
          show_docstring_returns: false
          show_source: false
          heading_level: 0

