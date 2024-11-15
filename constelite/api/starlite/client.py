from typing import Any, List, Union, Optional

import os

import requests.exceptions
from pydantic.v1 import BaseModel, Extra

from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from constelite.models import resolve_model, StateModel, StaticTypes

from loguru import logger


def resolve_return_value(data) -> Union[StateModel, List[StateModel], StaticTypes]:
    """
    Resolves the return value of the Starlite API.

    Arguments:
        data: The return value of the Starlite API.
    
    Returns:
        Data converted to state models
    """
    if isinstance(data, dict) and 'model_name' in data:
        return resolve_model(values=data)
    if isinstance(data, list):
        return [
            resolve_return_value(data=item)
            for item in data
        ]
    else:
        return data


class RequestModel(BaseModel, extra=Extra.allow):
    """
    A dummy model for sending requests to the Starlite API.

    Used for serialisation of the arguments to JSON using pydantic.
    """
    pass

class StarliteClientEndpoint:
    """
    Callable endpoint of the Starlite API that converts passed kwargs
    to a JSON payload and sends to the defined endpoint.

    Can be extended by accessing attributes of the endpoints, which will generate
    new endpoints recursively. For example

    ```python

    my_endpoint = StarliteClientEndpoint(client, endpoint='my_endpoint')
    sub_endpoint = my_endpoint.sub_endpoint
    ```

    sub_endpoint represents '.../my_endpoint/sub_endpoint'.

    Arguments:
        client: ConsteliteAPI instance.
        endpoint: Endpoint of the Starlite API.
        is_root: Whether the endpoint is a root endpoint.
    """
    def __init__(self, client, endpoint, is_root=False):
        self.client = client
        self.is_root=is_root
        self.endpoint = endpoint
        self.url = os.path.join(client.url, endpoint)
    
    def __getattr__(self, key):
        return self.__class__(
            client=self.client,
            endpoint=os.path.join(self.endpoint, key)
        )

    def _call(self, wait_for_response=True, **kwargs) -> Any:
        """
        Calls the endpoint and handles the response.
        Arguments:
            wait_for_response: If False, will post the request but not wait
              for the response to come back. Will return the string
              "request sent".

        Returns:
            Return of the endpoint converted to state models if necessary.
        
        Raises:
            SystemError: If the endpoint returns a 500 or 400 error.
        """
        obj = RequestModel(**kwargs)

        if not wait_for_response:
            try:
                ret = self.client._http.post(
                    self.url,
                    data=obj.json(),
                    headers={
                        "Authorization": f"Bearer {self.client.token}"
                    },
                    # Large timeout for the connection
                    # We don't wait for the response so small timeout for read
                    timeout=(12.05, 0.001)
                )
            except requests.exceptions.ReadTimeout as e:
                # Only catch the Read Timeout
                return
        else:
            ret = self.client._http.post(
                self.url,
                data=obj.json(),
                headers={
                    "Authorization": f"Bearer {self.client.token}"
                }
            )
 
        if ret.status_code == 201:
            if ret.text != '':
                data = ret.json()
                return resolve_return_value(data=data)
        elif ret.status_code == 500 or ret.status_code == 400:
            data = ret.json()
            
            log_message = f"Request failed with status code {ret.status_code}"

            if (
                (extra:=data.get('extra', None)) is not None
                and (error_message:=extra.get('error_message', None)) is not None
            ):
                log_message += f"\nError: {error_message}"

            logger.error(log_message)

            if extra and (traceback:=extra.get('traceback', None)) is not None:
                logger.debug(f"Traceback:\n{traceback}")

            raise SystemError(data['detail'])
        elif ret.status_code == 404:
            logger.error(f"URL {self.url} is not found")
            raise SystemError("Invalid url")
        else:
            logger.error(
                f"Failed to receive a response. {ret.status_code}: {ret.text}"
            )
            raise SystemError("Failed to receive a response")
    def __call__(self, wait_for_response=True, **kwargs) -> Any:
        return self._call(wait_for_response=wait_for_response, **kwargs)

class ProtocolsEndpoint(StarliteClientEndpoint):
    """
    Special endpoint class for sending protocol requests.
    """
    def __call__(self, wait_for_response=True, **kwargs) -> Any:
        logger = kwargs.pop('logger', None)
        args = kwargs

        return self._call(wait_for_response=wait_for_response, args=args, logger=logger)

class JobsEndpoint(ProtocolsEndpoint):
    """
    Special endpoint class for sending job requests.
    """
    @property
    def fetch(self):
        return StarliteClientEndpoint(
            client=self.client,
            endpoint="jobs/fetch"
        )
class StarliteClient:
    def __init__(self, url: str, token: Optional[str] = None):
        self.url = url
        self.token = token or os.environ.get('CONSTELITE_TOKEN', None)
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._http = Session()

        self._http.mount("https://", adapter)
    
    @property
    def protocols(self) -> StarliteClientEndpoint:
        return ProtocolsEndpoint(
            client=self,
            endpoint="protocols",
            is_root=True
        )

    @property
    def jobs(self) -> StarliteClientEndpoint:
        return JobsEndpoint(
            client=self,
            endpoint="jobs",
            is_root=True
        )

    def __getattr__(self, key) -> "StarliteClient":
        return StarliteClientEndpoint(
            client=self,
            endpoint=key,
            is_root=True
        )
