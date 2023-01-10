import os

from pydantic import BaseModel, Extra

from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from constelite.models import resolve_model


class RequestModel(BaseModel, extra=Extra.allow):
    pass


class StarliteClient:
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

    @property
    def getter(self):
        return StarliteClient(url=os.path.join(self.url, 'getter'))

    @property
    def protocol(self):
        return StarliteClient(url=os.path.join(self.url, 'protocol'))

    @property
    def setter(self):
        return StarliteClient(url=os.path.join(self.url, 'setter'))

    @property
    def store(self):
        return StarliteClient(url=os.path.join(self.url, 'store'))

    def __getattr__(self, key):
        def wrapper(**kwargs):
            path = os.path.join(self.url, key)
            obj = RequestModel(**kwargs)

            ret = self._http.post(
                path,
                data=obj.json()
            )

            if ret.status_code == 201:
                if ret.text != '':
                    data = ret.json()
                    return resolve_model(values=data)
                    # ref = data.pop('ref', None)
                    # if ref is not None:
                    #     return Ref(ref=ref)
                    # return StateModel.resolve(values=data)
            else:
                raise Exception(f"Failed to call remote method\n {ret.text}")
        return wrapper
