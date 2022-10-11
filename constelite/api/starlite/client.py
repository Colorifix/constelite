import os

from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from constelite import FlexibleModel


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

    def __getattr__(self, key):
        def wrapper(**kwargs):
            path = os.path.join(self.url, key)

            obj = FlexibleModel(**kwargs)

            ret = self._http.post(
                path,
                data=obj.json()
            )

            if ret.status_code == 201:
                if ret.text != '':
                    return FlexibleModel(**ret.json())
            else:
                raise Exception(f"Failed to call remote method\n {ret.text}")
        return wrapper
