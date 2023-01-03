import os
import toml


def get_config(config_ref: str):
    from constelite.models.model import ConsteliteBaseModel

    env = os.getenv("API_CONFIG", ".config")
    try:
        config = toml.load(env)
        data = config[config_ref]
        return ConsteliteBaseModel.resolve(values=data, force=True)
    except toml.TomlDecodeError as e:
        raise BaseException(f"Invalid config: {str(e)}")
