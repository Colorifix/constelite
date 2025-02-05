## Intro
Relationships is a way how models are connected logically together. It should be a familiar concept if you've done any data modeling before.

For example, we might have two models `Cat` and `Human`. We can add a relation to `Cat` with name 'carer' that would create a link between a `Cat` and the `Human` who takes care of the cat.

```python
from constelite.models import StateModel, Relationship

class Human(StateModel):
    name: str

class Cat(StateModel):
    name: str
    carer: Relationship[Human]
```

Note that although we use `Relationship[Human]` as a type of `carer`, relationships are nothing but a fancy wrapper around the list of references.

## Types of relationships

In practice, we never use `Relationship` type directly. Instead, we differentiate between three types of relationships: Association, Aggregation and Composition.

Relationship types behave differently when used in combination with the store methods, so it is important to understand the difference between them.

Let's go through them one by one.

### Association

The simplest of the three types. This is when we want to say one state is associated with another. Apart from that, the two related states are totally independent. `Cat->Human` relationship that we used in the example is an Association.

If we apply `PUT` or `PATCH` operation on association, it's values will be overwritten. For example

```python

r_cat.carer = [ref(Human(name="Lisa"))]
client.store.patch(ref=r_cat)
```

Would remove any old relationships between the `r_cat` and any carers and assign Lisa as the only carer.

And if we were to delete the record of the cat, Lisa would be unaffected (in data modelling sense; I'm sure she would be very sad to loose her cat).

### Aggregation

Aggregation is usually used to represent collection of states. For example, we might might have a state `CatGang` that represents an organisation of cats.

```python

class CatGang(StateModel):
    members: Aggregation[Cat]
```

In this relationship, cats are still relatively independent of the gang. They would be relatively unaffected if the gang would stop existing. This feature is the main difference that separates Aggregation from Composition.

When we apply PUT operation on Aggregation we overwrite the members same as in Association. However, when we apply PATH, we add new members to the Aggregation without affecting any existing members. This can be useful when you want to add a new relationship without first fetching all the existing ones.

When we apply DELETE operation on the collection, e.g. the gang of cats, all the members stay intact.

### Composition

Composition is also used to represent collections but in a stronger sense. In particular, the members of the collection can not exist without the collection itself. For example, we might have:

```python
class Page(StateModel):
    index: int

class Book(StateModel):
    pages: Composition[Page]
```

If we would delete the book, the pages that belonged to the book would disappear together with the book.

Composition behaves the same as Aggregation when we apply PATH, i.e. it will add new members to the collection without affecting the existing members.

When we apply PUT to Composition we will overwrite the old members with new (as in Aggregation) but in addition, all old members will be deleted.

When we apply DELETE to the collection that has a Composition relation, all members of the Composition will be deleted as well.

## Backrefs

Backrefs are special kind of relationships. Let's see how they can be useful in our case. We currently record the carer of the cat, but we have no way of figuring out how many cats does a particular `Human` takes care of. We can change that by adding a Backref.

```python
from constelite.models import StateModel, Relationship, backref

class Human(StateModel):
    name: str
    cats: backref(model="Cat", from_field="carer")

class Cat(StateModel):
    name: str
    carer: Association[Human]
```

Now we can access all cats that a human takes care of through `Human.cats` field.

!!! note
    Backrefs are created when we assign `carer` to the `Cat`. Assigning `cats` on `Human` will have no effect neither on the human nor the cat.
