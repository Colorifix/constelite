[GraphQL](https://graphql.org/) is a language for defining queries (and other things, but we are just 
using the query part for now).

## Running GraphQL queries

GraphQL can be used to fetch a set of related models and particular
models fields of interest. For certain queries, it may be more convenient or 
more efficient than using the store query or get methods. 

Say we have models for humans and cats, and we have some data in one of our stores. 
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

We could define a GraphQL query that describes which type of data to fetch 
(cats), how to filter the data (name=Snowball), and the model fields to return. 
Fields of related models can also be fetched (the name of the owner). 
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
A GraphQL query returns the data in a standard format: 
```
{
    'data': {
        'cats': [
            {  
              'state': {
                'name': 'Snowball', 
                'age': 5, 
                'owner': {
                    'name': 'Lisa'
                }
              }
            }
        ]
    }
}
```
Depending on the Constelite endpoint or store function used, the data will 
either be returned in this dictionary format (`store/graphql`) or in the 
format of a list of Constelite Ref models (`store/graphql_models`). 

### DataLoaders
One major benefit of GraphQL is its compatibility with 
[DataLoaders](https://github.com/syrusakbary/aiodataloader). Data loaders make 
sure that each bit of data is loaded only once during a query. 

For example, say our store contains two cats, both owned by Lisa.   
This is our query: 
```
{
    cats {
        state {
          name
          age
          owner {
            name
          }
        }
}
```
and this is the data to return:
```
{
    'data': {
        'cats': [
            {  
              'state': {
                'name': 'Snowball', 
                'age': 5, 
                'owner': {
                    'name': 'Lisa'
                }
              }
            }, 
            {  
              'state': {
                'name': 'Snowball II', 
                'age': 1, 
                'owner': {
                    'name': 'Lisa'
                }
              }
            }
        ]
    }
}
```
For both of these cats, the owner is Lisa. The naive method of fetching the 
data would first find both cats, then fetch the owner of Snowball (Lisa), then
fetch the owner of Snowball II (also Lisa). We have therefore had to fetch the same 
data for Lisa twice from the database (google GraphQL N + 1 problem if you are interested). 
The data loader would wait until we have collected all the cat owners, 
and only fetch the data for each unique owner once.  

When we have large queries with lots of related models, data loaders can 
substantially reduce the number of get operations we need to run. 


### store/graphql 
We can use the `store.graphql` function or `/store/graphql` endpoint to return 
data in the GraphQL format. This may be useful for use with external tools 
(e.g grafana has a GraphQL plugin). 

Each model field can be used to filter the data. Currently only uids and guids 
can be used with lists of values for "IN" filters. 

```python
from constelite.api import StarliteClient
from constelite.models import StoreModel
from constelite.graphql.utils import GraphQLQuery


if __name__ == "__main__":
    client = StarliteClient(url="http://127.0.0.1:8083")

    results = client.store.graphql(
        query=GraphQLQuery(
            query_string="""
            query {
                dnasamples (barcode: "2118717660") {
                    guid
                    record {
                        uid
                    }
                    state {
                        barcode
                        location {
                            guid
                            record {
                                uid
                            }
                            state {
                                model_name
                                name
                                barcode
                            }
                        }
                    }
                }
            }
            """),
        store=StoreModel(uid="2ca044b7-019d-4c23-a153-145e44352b6a")
    )
```
The results will be returned in a dictionary
```python
{'data': {
    'dnasamples': [
        {
            'guid': '1bc3313d-b288-41a3-8f0d-530dd9290ca8', 
            'record': {
                'uid': '27bb353f-a9f1-4d78-a9e5-de3bdb316f8a'
            }, 
            'state': {
                'barcode': '2118717660', 
                'location': [
                    {
                        'guid': '06f0ebba-3dd7-4e3b-86e1-e8c15aae09f4', 
                        'record': {
                            'uid': 'b8218668-1c98-4040-8f0c-ccf832cc709c'
                        }, 
                        'state': {
                            'model_name': 'BarcodedLocation', 
                            'name': '[TEST] SBS rack', 
                            'barcode': 'TS01751053'
                        }
                    }
                ]
            }
        }
    ]
}}
```

### store/graphql_models
The `store.graphql_models` function or `/store/graphql_models` endpoint 
converts the GraphQL data into Constelite `Ref` models before returning it. 
It will act much like a normal store query except you can
fetch related models at the same time.   

The queries can be defined with a query string. In this case, the query string
must contain the fields that define the Ref object, as well as any fields you
are interested in from the state model. 

```python
from constelite.api import StarliteClient
from constelite.models import StoreModel
from colorifix_alpha.models import DNASample
from constelite.graphql.utils import GraphQLModelQuery

if __name__ == '__main__':
    client = StarliteClient(url="http://127.0.0.1:8083")
    
    results = client.store.graphql_models(
        query=GraphQLModelQuery(
            query_string="""
            query {
                dnasamples (barcode: "2118717660") {
                    model_name
                    guid
                    record {
                        uid
                        store {
                            uid
                        }
                    }
                    state_model_name
                    state {
                        model_name
                        barcode
                        location {
                            model_name
                            record {
                               uid
                               store {
                                    uid
                                }
                            }
                            guid
                            state_model_name
                            state {
                                model_name
                                name
                            }
                        }
                    }
                }
            }
            """,
            state_model_name='DNASample'
        ),
        store=StoreModel(uid="2ca044b7-019d-4c23-a153-145e44352b6a")
    )
    for r in results:
        print(r)
```
results are in the format of a `Ref` model
```python
record=StoreRecordModel(store=StoreModel(uid=UUID('2ca044b7-019d-4c23-a153-145e44352b6a'), name=None), uid='27bb353f-a9f1-4d78-a9e5-de3bdb316f8a') guid=UUID('1bc3313d-b288-41a3-8f0d-530dd9290ca8') state=DNASample(model_name='DNASample', barcode='2118717660', photos=None, location=[Ref[BarcodedLocation](record=StoreRecordModel(store=StoreModel(uid=UUID('2ca044b7-019d-4c23-a153-145e44352b6a'), name=None), uid='b8218668-1c98-4040-8f0c-ccf832cc709c'), guid=UUID('06f0ebba-3dd7-4e3b-86e1-e8c15aae09f4'), state=BarcodedLocation(model_name='BarcodedLocation', name='[TEST] SBS rack', location_type=None, barcode=None, orientation_barcode=None, samples=None), state_model_name='BarcodedLocation', model_name='Ref')], position=None, dna=None, used_in_cbs_cycle=None, output_from_cbs_cycle=None) state_model_name='DNASample' model_name='Ref'
```

You can also define the queries without having to write out the full string. 
This uses the package [graphql_query](https://github.com/denisart/graphql-query). 
You can define fields to fetch using either the field name, or a 
`graphql_query.Field` object if you want to fetch the fields of a related model. 
The fields required for creating the Ref object are added to the query for you, 
so you only have to define the fields you want to fetch from the state model. 

This will create and run the same query as the example above where the 
query string was written out in full.  

```python

from constelite.api import StarliteClient
from constelite.models import StoreModel
from colorifix_alpha.models import DNASample
from constelite.graphql.utils import GraphQLModelQuery
import graphql_query


if __name__ == '__main__':
    client = StarliteClient(url="http://127.0.0.1:8083")
    results = client.store.graphql_models(
        query=GraphQLModelQuery(
            fields=[
                'barcode',
                graphql_query.Field(name="location", fields=['name'])
            ],
            arguments={'barcode': '"2118717660"'},
            state_model_name='DNASample'
        ),
        store=StoreModel(uid="2ca044b7-019d-4c23-a153-145e44352b6a")
    )
    for r in results:
        print(r)
```



