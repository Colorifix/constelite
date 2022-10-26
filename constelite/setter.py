from typing import List, Optional

from pydantic import validate_arguments, create_model

from constelite import get_config, SetterAPIModel

from loguru import logger


class setter:
    """Wrapper for setters
    """
    __setters: List[SetterAPIModel] = []

    @classmethod
    @property
    def setters(cls) -> List[SetterAPIModel]:
        return cls.__setters

    def __init__(self, name: str = None):
        self.name = name

    @logger.catch(reraise=True)
    def __call__(self, fn):
        fn_name = fn.__name__

        if fn_name in self.__setters:
            logger.warn(f"Duplicate of {fn_name} found. Skipping...")
            return fn
        else:
            set_model = fn.__annotations__.get('model', None)

            if set_model is None:
                raise ValueError(
                    f"Getter function {fn_name} has no 'model' argument."
                )

            config_model = fn.__annotations__.get('config', None)

            fn_model = create_model(
                fn.__name__,
                model=(set_model, ...),
                config=(Optional[config_model], None)
            )

            def wrapper(**kwargs):
                config = kwargs.get('config', None)
                if config is None:
                    kwargs['config'] = get_config(config_model)

                return validate_arguments(fn)(**kwargs)

            path = fn.__name__
            wrapper.__name__ = path

            self.__setters.append(
                SetterAPIModel(
                    path=path,
                    name=self.name,
                    set_model=set_model,
                    fn=wrapper,
                    fn_model=fn_model,
                    config=config_model
                )
            )

            return wrapper
