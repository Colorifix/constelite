import arq
from loguru import logger
from arq.worker import Function
from arq.connections import RedisSettings
from constelite.api import ConsteliteAPI
from typing import Optional, List, Type, Dict, Any
from constelite.store import BaseStore, AsyncBaseStore
from constelite.guid_map import GUIDMap, AsyncGUIDMap
from constelite.loggers.base_logger import Logger
import inspect
from pydantic.v1 import BaseModel, Extra
import pickle
import json
import os
from socket import gethostname
from constelite.api.camunda.defs import (
    CONSTELITE_ENV_EVN_VARIABLE   # Same var as Camunda uses
)


class RedisJobModel(BaseModel, extra=Extra.allow):
    """
    A dummy model for sending requests to the Starlite API.

    Used for serialisation of the arguments to JSON using pydantic.
    """
    pass


def serializer(data: dict[str, Any]):
    obj = RedisJobModel(**data)
    return pickle.dumps(obj.json())


def deserializer(data):
    # Let the protocols convert the data
    return json.loads(pickle.loads(data))


def get_worker_settings(redis_settings: RedisSettings):
    return type(
        "WorkerSettings",
        (object,),
        dict(
            functions=['run_protocol'],
            job_serializer=serializer,
            job_deserializer=deserializer,
            redis_settings=redis_settings,
            # Only take jobs from the queue matching this Constelite Env
            queue_name=os.environ.get(CONSTELITE_ENV_EVN_VARIABLE,
                                      gethostname()),
            # Clear jobs immediately one completed,
            # so we can run another with the same id
            keep_result=0
        )
    )


async def get_redis_pool(redis_settings: RedisSettings):
    return await arq.create_pool(
        redis_settings,
        job_serializer=serializer,
        job_deserializer=deserializer
    )


class ConsteliteWorker(arq.Worker):
    """
    A bit of extra logic about the arq worker to pass the API and set up the
    function.
    Only runs the run_protocol function.
    """
    def __init__(self, api, functions, *args, **kwargs):
        self.api = api
        functions = [self.get_general_protocol_function()]
        super().__init__(functions, *args, **kwargs)

    def get_general_protocol_function(self) \
            -> Function:
        """
        Wraps the run_protocol function of the ConsteliteAPI in a way that
        arq likes it.

        """
        # Create an async function that also takes the ctx argument.
        # Sort out the logger at the same time.
        async def coroutine(ctx, **kwargs):
            kwargs["logger"] = await self.api.get_logger(
                kwargs.get("logger", None)
            )
            # Resolve the arguments to Constelite models
            protocol = self.api.get_protocol(slug=kwargs['slug'])
            resolved_kwargs = protocol.fn_model(**kwargs)

            for k in resolved_kwargs.__fields__.keys():
                kwargs[k] = getattr(resolved_kwargs, k, None)

            try:
                await self.api.run_protocol(**kwargs)
            except Exception as e:
                logger.error(
                    f"Failed to run protocol {kwargs['slug']}, {str(e)}"
                )

        return Function(
            'run_protocol', coroutine,
            timeout_s=None, keep_result_s=None,
            keep_result_forever=None, max_tries=None
        )


class RedisAPI(ConsteliteAPI):

    def __init__(self,
        name: str,
        version: Optional[str] = None,
        stores: Optional[List[BaseStore | AsyncBaseStore]] = [],
        temp_store: Optional[BaseStore] = None,
        dependencies: Optional[Dict[str, Any]] = {},
        guid_map: Optional[GUIDMap] = None,
        async_guid_map: Optional[AsyncGUIDMap] = None,
        loggers: Optional[List[Type[Logger]]] = None,
        redis_settings: Optional[RedisSettings] = None
    ):

        super().__init__(
            name=name,
            version=version,
            stores=stores,
            temp_store=temp_store,
            dependencies=dependencies,
            guid_map=guid_map,
            async_guid_map=async_guid_map,
            loggers=loggers
        )

        self.settings_cls = get_worker_settings(redis_settings=redis_settings)

    def get_kwargs(self) -> Dict[str, NameError]:
        worker_args = set(inspect.signature(arq.Worker).parameters.keys())
        d = self.settings_cls if isinstance(self.settings_cls, dict) else \
            self.settings_cls.__dict__
        return {k: v for k, v in d.items() if k in worker_args}

    def create_worker(self, **kwargs: Any) -> arq.Worker:
        return ConsteliteWorker(
            api=self, **{**self.get_kwargs(), **kwargs})

    def run(self, **kwargs: Any) -> arq.Worker:
        worker = self.create_worker(**kwargs)
        logger.info("Running Redis worker")
        worker.run()
        return worker

