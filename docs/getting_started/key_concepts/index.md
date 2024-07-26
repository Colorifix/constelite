# Key concepts


Here are some key concepts we use in Constelite:

[State model](state_model.md)

:   A model of object's state defined as a Python class derived from [`StateModel`][constelite.models.StateModel].

[Store](store.md)

:   An abstraction that defines a common interface to data provider.

[Reference](ref.md)

:   A reference to an object available from a particular data provider.

[Protocol](protocol.md)

:   A python method that converts one object state to another independent of the data provider.

[API](api.md)

:   An API that serves `Stores` and `Protocol` to users.

[Hook](hook.md)

:   An async python method that can emit a message through the API when an event happens.
