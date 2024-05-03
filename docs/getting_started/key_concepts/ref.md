# Reference

## Intro

References are... well, references to records about an entity in the particular store. Think of them as primary keys, indexes or pointers that identify the record but not necessarily hold the state of the record.

## Why do we need references?

Constelite is meant to run on a remote server that has access to all the stores and exposes an API for clients to execute functions (also on the server).

Without references you, as a Constelite client, would have to instruct the server to retrieve the state from a store, send it to you so you can send it back to the server as an argument to the API function.

With references, you can avoid sending the state (which can be a big) back-and-forth between the server and the client.

## Anatomy of a reference

Reference holds information about the store record, i.e. what is the uid of the record and uid of the store the record is in.

In addition, references might contain the state. The state might represent a snapshot of the record, e.g. when you retrieved a record from a store using `put()` or it might represent a partial state that you can use for `patch()` or `put()`.

Below is an example of a serialized `r_cat: Ref[Cat]` object without a state:

```json
{
    "record": {
        "uid": "0af5e0c7-9b81-4abb-9b2b-8d373e263461",
        "store":{
            "name": "NotionStore",
            "uid": "68550a51-f1b7-456b-8ed3-4b0f7a7f810c"
        }
    },
    "model_name": "Ref",
    "state_model_name": "Cat",
    "state": null
}
```
This reference tells us that it points to a record `0af5e0c7-9b81-4abb-9b2b-8d373e263461` in the Notion store and the type of the record is `Cat`.

We can use this reference to retrieve the state of the record:

```py
r_cat = store.get(ref=r_cat)
```

!!! note
    By convention, all references are prefixed with `r_` so it easier to distinguish them from states. 


which will transform the reference to:

```json
{
    "record": {
        "uid": "0af5e0c7-9b81-4abb-9b2b-8d373e263461",
        "store":{
            "name": "NotionStore",
            "uid": "68550a51-f1b7-456b-8ed3-4b0f7a7f810c"
        }
    },
    "model_name": "Ref",
    "state_model_name": "Cat",
    "state": {
        "name": "Snowball",
        "model_name": "Cat"
    }
}
```

!!! note
    You can access properties of the reference's state directly, e.g.

    ```py
    assert r_cat.name == "Snowball" 
    ```

## Global identifier

One extra piece of information the reference can hold is a global unique identifier (guid).

The difference between the reference uid and reference guid is that the former uniquely identifies the record in a particular store, while the latter uniquely identifies the entity the record belongs to. Confusing, isn't it?

Let's take the cat called "Snowball" as an example. Snowball is an unique entity. There is no other cat like her. Let's give her a microchip that hold her global unique identifier (4b0f7a7f810c). In the vet's database, Snowball is known as patient "304059" (her unique identifier in the database). If Snowball moves to another country, she might register with another vet and have a different uid in the new database.

Reference always points to a particular record in a particular database, but it also contains information about the entity that the records belongs to.