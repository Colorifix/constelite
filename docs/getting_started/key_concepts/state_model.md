# State Model

## Intro

Think of them as ORM classes but without any particular back-end. They are just classes that define what properties and relationships object can have.

```python
from typing import Optional
from constelite.models import StateModel, Association


class Creature(StateModel):
    name: Optional[str]


class Human(Creature):
    age: Optional[int]


class Cat(Creature):
    owner: Optional[Association[Human]]

    def mew(self):
        print(f"{self.name} says mew!")
```

## Why Optional ?

Indeed... All fields of [`StateModel`][constelite.models.StateModel] should be optional to allow exchange of 'partial state models'. Partial states are used when we want to update only certain fields on an object. For example, we might want to only update the name of a cat and not their owner. We would do so by invoking a `patch` method of a store:

```python
r_cat = ref(Cat(name='New name'))

store.patch(ref=r_cat)
```

By allowing partial states we avoid necessity to retrieve an object state from store before editing it. Hence minimizing amount of data we transport over the network.


## Model resolution

Let's dump a [`StateModel`][constelite.models.StateModel]

```python
>>> cat = Cat(name="Snowball")
>>> cat.json()
'{"model_name": "Cat", "name": "Snowball"}'
```

You will notice a `model_name` field that we haven't defined in the `Cat` state model. This field is generated automatically and takes the value of the state model name.

This is how constelite can resolve serialized objects without explicitly defying what model they should be resolved to. This is particularly useful when we are dealing with subclasses, like `Cat(Creature)`.

Let's see how it works

```python
from constelite.models import resolve_model

>>> model_dict = {"model_name": "Cat", "name": "Snowball"}
>>> cat = resolve_model(model_dict)
>>> cat
Cat(model_name='Cat', name='Snowball')
>>> cat.mew()
Snowball says mew!
```