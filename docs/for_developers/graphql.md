## GraphQL implementation

GraphQL servers are often based on a GraphQL schema or a set of models defined
in a GraphQL package such as 
[Graphene](https://github.com/graphql-python/graphene). Since we already have
our models defined in Pydantic, we start from our StateModels and convert them
into a GraphQL schema.  

This is done by converting the Pydantic models into Graphene models, since 
Graphene have dealt with the issue of recursive relationships between models. 
We may be able to remove Graphene from the process if we implement our own 
solution to that problem.  

The conversion to Graphene models is done dynamically when the app is started. 
This means we don't have to write the GraphQL models or schema ourselves, 
and it is kept up to date with any changes we have made to the Constelite 
data model. The conversion is done using the 
`constelite.graphql.schema.GraphQLSchemaManager` class, which is
also used to supply the schema and data loaders when a GraphQL query is run on 
a store. 

Since we are creating Graphene models, reading the 
[Graphene docs](https://docs.graphene-python.org/en/latest/quickstart/#) will 
help to explain the main concepts.   


For the examples below, I'll use this set of StateModels:
```python
from typing import Optional
from constelite.models import StateModel, Association


class Creature(StateModel):
    name: Optional[str]


class Human(Creature):
    age: Optional[int]


class Cat(Creature):
    owner: Optional[Association[Human]]
```

### Conversion to Graphene Models

The StateModels are converted to Graphene models. The field types from the 
StateModels are converted to the equivalent GraphQL types. 

The data we are fetching through Constelite are actually returned as `Ref` 
models, which have a record and a state. We
therefore mirror this structure with our Graphene models. Where we use generics 
with Refs to produce `Ref[Cat]` and `Ref[Human]`, we instead create separate 
Graphene models.

We have a Graphene equivalent of the Record and StoreModels defined in 
`constelite.graphql.schema`:

```python
import graphene

class StoreModelGQL(graphene.ObjectType):
    uid = graphene.String()
    name = graphene.String()

class RecordGQL(graphene.ObjectType):
    uid = graphene.String()
    store = graphene.Field(StoreModelGQL)
```

The rest of the models are dynamically generated. For the StateModels above, 
classes like the following will be dynamically generated:

```python
import graphene


class CreatureGQLstate(graphene.ObjectType):  # Equivalent of Creature
    model_name = graphene.String()
    name = graphene.String()

class CreatureGQL(graphene.ObjectType):  # Equivalent of Ref[Creature]
    model_name = graphene.String()
    guid = graphene.String()
    record = graphene.Field(RecordGQL)
    state_model_name = graphene.String()
    state = graphene.Field(CreatureGQLstate)
    
    def resolve_state(parent, info):
        state = parent.state
        if state is None:
            context = info.context
            dataloader = context.get('dataloaders').get("Creature")
            loaded_ref = await dataloader.load(parent.uid)
            state = loaded_ref.state

        return state
   
class HumanGQLstate(graphene.ObjectType):
    model_name = graphene.String()
    name = graphene.String()
    age = graphene.Int()
    
class HumanGQL(graphene.ObjectType): 
    model_name = graphene.String()
    guid = graphene.String()
    record = graphene.Field(RecordGQL)
    state_model_name = graphene.String()
    state = graphene.Field(HumanGQLstate)
    
    def resolve_state(parent, info):
        state = parent.state
        if state is None:
            context = info.context
            dataloader = context.get('dataloaders').get("Human")
            loaded_ref = await dataloader.load(parent.uid)
            state = loaded_ref.state

        return state
    
class CatGQLstate(graphene.ObjectType):
    model_name = graphene.String()
    name = graphene.String()
    age = graphene.Int()
    owner = graphene.List(HumanGQL)
    
class CatGQL(graphene.ObjectType): 
    model_name = graphene.String()
    guid = graphene.String()
    record = graphene.Field(RecordGQL)
    state_model_name = graphene.String()
    state = graphene.Field(CatGQLstate)
    
    def resolve_state(parent, info):
        state = parent.state
        if state is None:
            context = info.context
            dataloader = context.get('dataloaders').get("Cat")
            loaded_ref = await dataloader.load(parent.uid)
            state = loaded_ref.state

        return state

```
Note that we don't use inheritance here. We just need to define the fields of 
the model, and the resolvers function to fetch the state if it is needed - 
see the resolver section below. The resolvers for the simple fields are 
automatically created by Graphene for us so we don't need to define them. 

Field types from Pydantic models are converted to GraphQL types using the 
`constelite.graphql.field_type_map.convert_to_graphql_type`. Any fields that
can't be converted by this function is excluded from the GraphQL schema and 
we won't be able to fetch them using the GraphQL queries. 

The conversion of relationship fields to `graphene.List(RelatedModelGQL)` can
be complicated if the `RelatedModelGQL` hasn't yet been created. And especially
complicated if `RelatedModelGQL` relates (directly or indirectly) back to the 
original model (e.g. if humans also had a relationship to the cat they own). 
In these cases, we create a function that acts as a placeholder, 
and Graphene resolves the models correctly when the full schema is created.

### Main GraphQL query class

The GraphQL schema is defined by a Query class. 
This defines all the queries we can run. We have three models, Creature, Human,
and Cat, and want to be able to query our stores for each model type. We define each 
query as a field of the Query model and a resolver method. The model fields
also define the arguments we can use in the resolver function. We currently 
use the field names, uids and guids as the arguments.

```python
import graphene

class Query(graphene.ObjectType):
    creatures = graphene.List(
        CreatureGQL,
        uid=graphene.String(), 
        uids=graphene.List(graphene.String),
        guid=graphene.String(), 
        guids=graphene.List(graphene.String),
        name=graphene.String()
    )
    humans = graphene.List(
        HumanGQL,
        uid=graphene.String(), 
        uids=graphene.List(graphene.String),
        guid=graphene.String(), 
        guids=graphene.List(graphene.String),
        name=graphene.String(), 
        age=graphene.Int()
    )
    cats = graphene.List(
        CatGQL,
        uid=graphene.String(), 
        uids=graphene.List(graphene.String),
        guid=graphene.String(), 
        guids=graphene.List(graphene.String),
        name=graphene.String(), 
        age=graphene.String(), 
        owner=graphene.String()   # Argument is the UID of the owner 
    )

    # the Resolver methods takes the GraphQL context (root, info) as well as
    # any additional arguments for the Field and returns data for the query Response
    def resolve_creatures(root, info, uid, uids, guid, guids, name):
        # Query the store using any arguments as filters
        # See the next section for an explanation of these functions
        ...

    def resolve_humans(root, info, uid, uids, guid, guids, name, age):
        ...
    
    def resolve_cats(root, info, uid, uids, guid, guids, name, age, owner):
        ...

```

Once the Query class is defined, we use it to create the GraphQL schema. 
```python
schema = graphene.Schema(query=Query)
```
This schema is then used to execute the queries. 

A traditional GraphQL schema can also be generated from our Graphene schema. 
`print(schema)`:
```GraphQL
type Query {
  statemodels(guid: String, uid: String, uids: [String], guids: [String], model_name: String): [StateModelGQL]
  creatures(guid: String, uid: String, uids: [String], guids: [String], model_name: String, name: String): [CreatureGQL]
  humans(guid: String, uid: String, uids: [String], guids: [String], model_name: String, name: String, age: int): [HumanGQL]
  cats(guid: String, uid: String, uids: [String], guids: [String], model_name: String, name: String, age: int, owner: String): [CatGQL]
}
 
type RecordGQL {
  uid: String
  store: StoreModelGQL
}

type StoreModelGQL {
  uid: String
  name: String
}

type CreatureGQL {
  model_name: String
  guid: String
  record: RecordGQL
  state_model_name: String
  state: CreatureGQLstate
}

type CreatureGQLstate {
  model_name: String
  name: String
}

type HumanGQL {
  model_name: String
  guid: String
  record: RecordGQL
  state_model_name: String
  state: HumanGQLstate
}

type HumanGQLstate {
  model_name: String
  name: String
  age: Int
}

type CatGQL {
  model_name: String
  guid: String
  record: RecordGQL
  state_model_name: String
  state: CatGQLstate
}

type CatGQLstate {
  model_name: String
  name: String
  age: Int
  owner: [HumanGQL]
}
```


### Resolver functions
To execute the queries, GraphQL needs to know how to use the arguments to the 
resolvers to fetch data from whichever data source it is that we want to use.  

There are two types of resolvers that we define:  

1. the resolver functions in the Query class, e.g. `Query.resolve_cats`
2. the resolver functions for fetching states, e.g. `CatGQL.resolve_state`

The resolver functions in the Query class are the starting points of GraphQL 
queries. We define the store and dataloaders they should use in the 
`store.execute_graphql` function, and these are retrieved in the resolver function
from `info.context`. If the resolvers are passed uids or guids as arguemnts, 
the resolver function runs `store.get` for each id, otherwise it 
runs `store.query` using any other resolver arguments as filters. 

The `resolve_state` functions are used when we need to fetch a value from a 
related model and therefore need to fetch the state of the related Ref. You can 
see examples in the Conversion to Graphene Models section above. 
The `resolve_state` functions use the dataloaders. Each dataloader
takes a list of UIDs as arguments and runs `store.get` for each uid. There 
is one dataloader defined for each Constelite StateModel class, and each runs 
only once after all Refs for that class are collected. 
E.g. if we have seven cats, and they are related
to owners with uids 1, 1, 2, 1, 2, 1, and 2, the dataloader for Humans
will run `store.get` only twice - once for uid 1 and once for uid 2.

### Creating GraphQL queries
GraphQL queries can be written as strings like this:
```
{
    cats (name: "Snowball") {
        state {
          name
          age
          owner {
            name
          }
        }
}
```
We have to use these strings when using the `store/graphql` endpoint. 

However, if we are using the GraphQL queries to fetch Constelite models from the 
`store/graphql_models` endpoint, we also need to make sure the fields required 
for the `Ref` model are included:
```
{
    cats (name: "Snowball") {
        guid
        model_name
        state_model_name
        record {
          uid
          store {
              uid
          }
        }
        state {
          name
          age
          owner {
            guid
            model_name
            state_model_name
            record {
                uid
                store {
                    uid
                }
            }
            state {
              model_name
              name
            }
          }
        }
}
```
This is quite a long string to type out just to ask for the name, age and 
owner's name.  

To make this easier the `GraphQLModelQuery` can also use the 
[graphql_query](https://github.com/denisart/graphql-query) package to generate
the GraphQL strings for us. The additional fields required for the definition
of the `Ref` model are automatically added. 

```python
import graphql_query
from constelite.graphql.utils import GraphQLModelQuery

GraphQLModelQuery(
        fields=[
            'name',
            'age',
            graphql_query.Field(name="owner", fields=['name'])
        ],
        arguments={'name': '"Snowball"'},
        state_model_name='Cat'
    )
```
will create the equivalent query as the string above. A query string
is created using recursive functions in the `GraphQLModelQuery` class and then 
used to execute the graphql query. 

### Overwriting GraphQL methods
Some databases can work with GraphQL queries directly 
(or with the use of a plugin), and we may not need to
use the schema and resolvers that we have defined above. In those cases, we
can overwrite the `execute_graphql` function to run GraphQL queries using more
efficient methods. 