from typing import Any

import os

from pydantic import BaseModel, Extra

from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from constelite.models import resolve_model


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

    def __call__(self, **kwargs) -> Any:
        obj = RequestModel(**kwargs)

        ret = self._http.post(
            self.url,
            data=obj.json()
        )

        if ret.status_code == 201:
            if ret.text != '':
                data = ret.json()
                if isinstance(data, dict) and 'model_name' in data:
                    return resolve_model(values=data)
                else:
                    return data
        elif ret.status_code == 500:
            raise SystemError(ret.json()['detail'])
