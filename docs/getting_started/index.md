# Getting started

Probably the best way to get started at the moment is to clone the project git repo.

```console
$ git clone git@gitlab.com:colorifix/constelite/constelite.git
```

The project is split into two parts:

* **constelite**: the core of constelite
* **colorifix-alpha**: models, protocols and stores related to Colorifix

!!! warning
    The core of constelite is complex and poorly documented. Try not to mess with it unless you know exactly what you are doing.

For development and tests, you can start a local instance of constelite:

```console

$ cd constelite
$ poetry install
$ poetry run constelite --config /Volumes/DockerShare/constelite_staging_config.json starlite start
```

!!! info
    You need an access to Colorifix SMB server to get the config.

!!! warning
    Avoid copying config locally and always use a mount of DockerShare. The config contains secrets and you don't want to explain why you were storing the secrets locally when they leak.

We use `constelite/colorifix_alpha/examples` as a collection of examples. It's a good choice for your demos and tests with local constelite instance.