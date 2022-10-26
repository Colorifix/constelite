# Welcome to Constelite

## Definitions

### Config

Configs are just clases that define configurations. They are based on `pydantic.BaseModel` and must have serializable fields. Config value are stored in `$API_CONFIG` file ('.config' by default) and are primarily used to auto-configure getters and setters.

### Model

Model is just a class that is derived from `constelite.Model`, which is your ordinary `pydantic.BaseModel`.

### Getter

A function wrapped in `@getter` that gets some data from somewhere and returns it to the user.

* Getters must not call setters or protocols.
* Gerrers may call other getters (not tested yet).
* Getters must return a model.
* Getters may use `config` attribute has has a special meaning. See below.


### Setter

A function wrapped in `@setter` that sets(writes) a model to somewhere.

* Apart from optional `config`, setters must have a single extra argument `model` with a typehint specifying a model type.
* Setters must not call getters or protocols.
* Setters may call other setters (not tested yet).
* Setters may use `config` attribute has has a special meaning. See below.

### Protocol

A function wrapped in `@protocol` that convers one or more models into another model.


* Protocols must not call getters or setters.
* Protocols must not call other protocols.
* Protocols must use type hints for all arguments.
* Protocols must have a return type specified.


### Store

Store allows to save models on the server for later use. Each stored model has a reference of type `Ref`. You can pass reference to setters and protocols instead of passing actual models. You can also ask protocol or getter to store the model and return you a reference insted by passing an extra `store = True` argument.

Currently, we are using `pickle` as a store engine. You can setup a directory where the models are saved by adjusting `[StoreConfig]` section of the `$API_CONFIG` file.

```toml
[StoreConfig]
path="/path/to/store"
```

## How to

### Define a new model

Constelite uses `pydantic`. All models in constelite should be defined from `constelite.Model` base class.


```python
from constelite import Model


class Gene(Model):
    seq: str
    name: str
    description: str
```

### Add a getter

Getters are just fancy functions that can use a special `config` attribute to store configutation model. All configs should be derived from `constelite.Config` class. The `config` value should be either supplied when calling a getter or defined in `$API_CONFIG` file (defaults to '.config'). If nether are specified default values set in the config class definition will be used.

Getter function must have type hints for `config` attribute as well as for the return type.


```python
from constelite import getter, Config
from model import Gene

from typing import Optional


class UniprotGetterConfig(Config):
    url: Optional[str] = 'http://uniprots.com'


@getter(name="Get Uniprot gene")
def get_uniprot_gene(config: UniprotGetterConfig, gene_id: str) -> Gene:
    return Gene(
        name=f"Uniprot gene {gene_id}",
        seq="ATG",
        description=f"Obtained from {config.url}"
    )
```

## Add a setter

Same as getter, just fancy function that can take `config` as an argument. Setters always have a `model` argument of the type of model they are setting. Setters must not return anything.

```python
from constelite import setter, Config, FlexibleModel
from model import Gene

from loguru import logger


class TerminalSetterConfig(Config):
    format_str: str = "{model.__class__.__name__}: {model}"


@setter()
def set_gene_to_terminal(config: TerminalSetterConfig, model: Gene):
    logger.info(config.format_str.format(model=model))


@setter()
def set_model_to_terminal(config: TerminalSetterConfig, model: FlexibleModel):
    logger.info(config.format_str.format(model=model))
```

### Add a protocol

Protocols are another type of fancy functions. No configs this time. Must have a type hint for the return type.

```python
from typing import List
from constelite import protocol
from model import Gene


@protocol(name='Combine genes')
def combine_genes(genes: List[Gene], name: str) -> Gene:
    return Gene(
        name=name,
        seq=''.join([gene.seq for gene in genes]),
        description=(
            f"Combination of "
            f"{', '.join([gene.name for gene in genes])}"
        )
    )
```

### Start a server

Constelite auto-discovers all getters, setters and protocols for you. Just make sure you import them.

```python
from constelite.api import StarliteAPI
from protocol import *
from getter import *
from setter import *

if __name__ == '__main__':
    api = StarliteAPI(
        name='Example Starlite API',
        version='0.0.1',
        port=8083
    )

    api.run()
```

This should start a `starlite` server and all the fancy functions are now serverd over HTTP. You can explore the API by navigating to `http://127.0.0.1:8083/schema`.

### Call remote functions

Easy, just create an instance of `StarliteClient` and use it to do the reemote calls. Make sure you have a server running first.

```python
from constelite.api import StarliteClient
from model import Gene
from getter import UniprotGetterConfig

if __name__ == '__main__':
    client = StarliteClient(url='http://127.0.0.1:8083')

    getter_config = UniprotGetterConfig(
        url='www'
    )

    geneA = client.getter.get_uniprot_gene(
        config=getter_config,
        gene_id='gene_a'
    ).asmodel(Gene)

    geneB = client.getter.get_uniprot_gene(gene_id='gene_b').asmodel(Gene)

    gene = client.protocol.combine_genes(
        genes=[
            geneA,
            geneB
        ],
        name='Gene C'
    )

    client.setter.set_model_to_terminal(model=gene)
``` 

The `StarliteClient.getter` gives you access to all the getters, `StarliteClient.setter` to all setters and `StarliteClient.protocol` ... you guesed it.

So if we want to call a

```python
@getter(name="Get Uniprot gene")
def get_uniprot_gene(config: UniprotGetterConfig, gene_id: str) -> Gene:
    ...
``` 
call `client.getter.get_uniprot_gene(gene_id='...')`

The remote calls can't resolve the return models (yet) so they will always return a `FlexbleModel` object or `None`. To convert `FlexibleModel` to the target model, you can use `FlexibleModel.asmodel()` method.

### Work with store

You can ask getter or protocol to sotre the returned model on the server and pass you the rerference instead.

```python

r_geneA = client.getter.get_uniprot_gene(gene_id='gene_a', store=True)


gene = client.protocol.combine_genes(
    genes=[
        r_geneA,
        geneB
    ],
    name='Gene C',
    store=True
)
```

Note that `ref_geneA` can be passed instead of an actual `Gene` model.

You can also pass reference to setter instead of the model

```python
client.setter.set_model_to_terminal(model=ref_geneA)
```

You can also work directly with the store to load or save models


```python
gene = client.store.load(ref=ref_geneA)
```

```python
r_GeneB = client.store.save(model=geneB)
```