from typing import Any

import os

import requests.exceptions
from pydantic import BaseModel, Extra

from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from constelite.models import resolve_model

from loguru import logger


class RequestModel(BaseModel, extra=Extra.allow):
    pass


class StarliteClient:
    """A python client for communicating with the Starlite API
    """
    def __init__(self, url: str):
        self.url = url
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._http = Session()

        self._http.mount("https://", adapter)

    def __getattr__(self, key) -> "StarliteClient":
        return StarliteClient(url=os.path.join(self.url, key))

    def resolve_return_value(self, data):
        if isinstance(data, dict) and 'model_name' in data:
            return resolve_model(values=data)
        if isinstance(data, list):
            return [
                self.resolve_return_value(data=item)
                for item in data
            ]
        else:
            return data

    def __call__(self, wait_for_response=True, **kwargs) -> Any:
        """

        Args:
            wait_for_response: If False, will post the request but not wait
              for the response to come back. Will return the string
              "request sent".
            **kwargs:

        Returns:

        """
        obj = RequestModel(**kwargs)

        if not wait_for_response:
            try:
                ret = self._http.post(
                    self.url,
                    data=obj.json(),
                    # Large timeout for the connection
                    # We don't wait for the response so small timeout for read
                    timeout=(12.05, 0.001)
                )
            except requests.exceptions.ReadTimeout as e:
                # Only catch the Read Timeout
                return
        else:
            ret = self._http.post(
                self.url,
                data=obj.json(),
            )

        if ret.status_code == 201:
            if ret.text != '':
                data = ret.json()
                return self.resolve_return_value(data=data)
        elif ret.status_code == 500 or ret.status_code == 400:
            data = ret.json()
            logger.error(data.get('extra', None))
            raise SystemError(data['detail'])
        elif ret.status_code == 404:
            logger.error(f"URL {self.url} is not found")
            raise SystemError("Invalid url")
        else:
            logger.error(
                f"Failed to receive a response. {ret.status_code}: {ret.text}"
            )
