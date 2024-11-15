from typing import Any
import asyncio

from pydantic.v1 import  UUID4

from pydantic.v1 import BaseModel

from litestar import post

from functools import wraps

from constelite.protocol import ProtocolModel

from constelite.api.starlite.controllers.models import Job, JobStatus
from constelite.api.starlite.controllers.generator import (
    generate_protocol_router
)

tasks: dict[UUID4, asyncio.Task] = {}

class JobRequest(BaseModel):
    job: Job


async def get_job(data: JobRequest) -> Job:
    """Gets a job from memory.

    Checks the status of the asyncio task and returs the job status,
    result and error accordingly.
    """
    job = data.job
    if job.uid is None:
        raise ValueError("Can't fetch job with no uid")

    task = tasks.get(job.uid, None)

    if task is not None:
        try:
            job.result = task.result()
            job.status = JobStatus.success
            tasks.pop(job.uid)
        except asyncio.InvalidStateError:
            job.status = JobStatus.submitted
            job.result = None
        except Exception as e:
            job.status = JobStatus.failed
            job.error = repr(e)

    else:
        raise ValueError(f"Job {job.uid} does not exist'")

    return job


def task_wrapper(protocol_model: ProtocolModel):
    """A wrapper for converting protocol models to a starlite endpoint
    that creates an asyncio Task for the protocol function.
    """
    @wraps(protocol_model.fn)
    async def wrapper(api: Any, logger, **kwargs) -> Job:
        task = asyncio.create_task(
            api.run_protocol(protocol_model.slug, logger, **kwargs)
            # protocol_model.fn(api, logger, **kwargs)
        )

        job = Job(status=JobStatus.submitted)

        tasks[job.uid] = task

        return job

    return wrapper


def task_protocol_router(api):
    return generate_protocol_router(
        api=api,
        path='/jobs',
        fn_wrapper=task_wrapper,
        tags=["Jobs"],
        extra_route_handlers=[
            post(
                path="/fetch"
            )(get_job)
        ]
    )
