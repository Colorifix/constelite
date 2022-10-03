# Alternative model for getters

## Adding a new model

Add a new model by creating a derivative of a `GetBaseModel` class

```python
from constelite import Model


class Protein(Model):
    seq: str
    name: str
    description: str
```

That's it!

## Adding a new getter

Each getter creates an interface to access a data source and retrieve entities in the form of standard models. Each getter can retrieve one or more types of entities.

First, create a getter config class that will store configuration of the getter. This can be used to store access tokens for the data source or any other configuration parameters that might be useful for getting the data.

```python
from constelite import Config

class UniprotGetterConfig(Config):
    url: Optional[str] = 'http://uniprot.com'
``` 
Here we define config for a Uniprot getter that will handle all requests to Uniprot. We will just keep a url for to the main resource, just in case it changes in future.

In this example, we define a default value of the url. This value can be overwritten by adding a record to the config file (`.config` or `$API_CONFIG`) or passing a `UniprotGetterConfig` object to the getter (will see later).

Now, create a new getter class

```python
from models import Protein, Gene
from constelite import Getter, getter

@getter([Protein, Gene])
class UniprotGetter(Getter[UniprotGetterConfig]):
    def get_protein(self, uniprot_id: str) -> Protein:
        return Protein(
            name=f"Uniprot protein {uniprot_id}",
            seq="AAA",
            description=f"Obtained from {self.config.url}"
        )

    def get_gene(self, gene_id: str) -> Gene:
        return Gene(
            name=f"Uniprot gene {gene_id}",
            seq="ATG",
            description=f"Obtained from {self.config.url}"
        )
```
The `@getter` wrapper informs that the getter can get `Gene` and `Protein` entities. It is therefore expected to have `get_protein` and `get_gene` methods. It is important to add type hints to the getter methods to enable auto-getter-resolution magic.

That's it.

## Adding a new setter

Each setter creates an interface to convert standard models into data stored in an external resource.

First, create a new `Config` for a setter.

```python
from constelite import Config


class TerminalSetterConfig(Config):
    format_str: str = "{model.__class__.__name__}: {model}"
```

Here, we create config for a simple setter that would print models to terminal

Now define a new `Setter`:

```python
from constelite import Setter
from models import Protein, Gene


class TerminalSetter(Setter[TerminalSetterConfig]):
    def set_protein(self, protein: Protein):
        print(self.config.format_str.format(model=protein))

    def set_gene(self, gene: Gene):
        print(self.config.format_str.format(model=gene))
```

Our setter can handle models of type `Protein` and `Gene`. All we need to do to support these models is create `set_protein` and `set_gene` methods.

We can also override the `Setter.set()` method to handle any model:

```python
from constelite import Setter
from constelite import Model


class UniversalTerminalSettter(Setter[TerminalSetterConfig]):
    def set(self, model: Model):
        print(self.config.format_str.format(model=model))
```

## Adding a new protocol

Nothing can be easier. Just define a new function wrapped in `protocol`. Remember, you can't use getters nor setters inside the protocol.

```python
from typing import List
from constelite import protocol
from models import Gene


@protocol(name='Combine genes')
def combine_genes(genes: List[Gene], name: str):
    return Gene(
        name=name,
        seq=''.join([gene.seq for gene in genes]),
        description=(
            f"Combination of "
            f"{', '.join([gene.name for gene in genes])}"
        )
    )
```

That's it !

## Adding a new job

Same as with protocols but you can use  getters, setters and protocols inside. Even call other jobs if you wish. Use `Job` as a base class.

```pyhon
from model import Gene
from protocol import combine_genes
from setter import TerminalSetter, TerminalSetterConfig
from getter import UniprotGetter, UniprotGetterConfig


def domesticate_gene_job(gene: Gene):
    gene_pre = Gene.get(gene_id="gene_a")

    gene_suf = Gene.get(
        gene_id="gene_b",
        getter_cls=UniprotGetter,
        config=UniprotGetterConfig(
            url="https://colorifix.com"
        )
    )

    gene = combine_genes(
        name=gene.name,
        genes=[gene_pre, gene, gene_suf]
    )

    gene.set(
        TerminalSetter,
        config=TerminalSetterConfig(
            format_str=(
                "Setting gene\n {model.name} - {model.description}\n>"
                "{model.seq}"
            )
        )
    )


if __name__ == "__main__":
    gene = Gene(
        name="Gene C",
        seq="ATTGCTGAT",
        description="Ad-hoc gene"
    )

    domesticate_gene_job(gene)
```

## How does it work ?

The magic is in the logic of the `get` and `set` methods.

The `get` method goes through all getters that were marked as dealing with `Protein` entities and calls their `get_protein` method until it finds one that passes validation with the arguments passed to the `get` method.

The `set` method, if not overridden, will attempt to call `set_protein` of the `TerminalSetter`.


We can also specify a particular getter to use by setting a `getter_cls` argument

```python
protein = Protein.get(getter_cls=UniprotGetter, uniprot_id="A0JP26")
```

Finally (as promised), we can pass a `config` argument to override the default config values.

```python
protein = Protein.get(
    config=UniprotGetterConfig(url="http://colorifix.com")
    getter_cls=UniprotGetter,
    uniprot_id="A0JP26"
)
protein.set(
    UniversalTerminalSettter,
    config={
        'format_str': 'Setting {model.__class__.__name__} to {model}'
    }
)
```
```bash
Setting Protein to seq='AAA' name='Uniprot protein A0JP26' description='Obtained from http://colorifix.com'
```

## Disclaimer

Haven't  actually tested with multiple getters for the same entity. So might crash somewhere, but should be doable in principle.




