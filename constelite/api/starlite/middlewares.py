from datetime import datetime, timedelta, UTC
from typing import Dict

from litestar import Request
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
from pydantic.v1 import BaseModel
from litestar.exceptions import NotAuthorizedException
import jwt
from jwt import DecodeError, ExpiredSignatureError
from colorifix_alpha.util import get_config


class Token(BaseModel):
    exp: datetime
    name: str


class JWToken:
    """Does all the token generation using PyJWT"""

    @classmethod
    def encode_token(cls, data: Dict[str, str], exp=None) -> str:
        """Method to generate an access token"""
        if exp is None:
            exp = datetime.now(UTC) + timedelta(
                minutes=get_config("security", "token_exp_min")
            )
        token = Token(**data, exp=exp)
        return jwt.encode(
            token.dict(),
            get_config("security", "secret_key"),
            algorithm=get_config("security", "algorithm")
        )

    @classmethod
    def decode_token(cls, token: str) -> Token:
        """Method to decode the access token"""
        try:
            return Token.parse_obj(
                jwt.decode(
                    token,
                    get_config("security", "secret_key"),
                    algorithms=get_config("security", "algorithm")
                )
            )
        except ExpiredSignatureError:
            raise NotAuthorizedException()
        except DecodeError:
            raise NotAuthorizedException()


class JWTAuthenticationMiddleware(AbstractAuthenticationMiddleware):
    async def attempt_jwt_authentication(self, raw_token) -> AuthenticationResult:
        # Retrieve and decode the token in the auth header
        token = JWToken.decode_token(raw_token)

        return AuthenticationResult(user=token.name, auth=raw_token)

    async def authenticate_request(self, request: Request) -> AuthenticationResult:
        """Given a request, parse the request api key stored
        in the header
        """
        
        if request.scope["method"] == "OPTIONS":
            return AuthenticationResult(user=None, auth=None)

        auth_header = request.headers.get("Authorization", "")

        if auth_header == "":
            raise NotAuthorizedException(detail="No 'Authorization' header provided")
        
        try:
            auth_scheme, raw_token = auth_header.split(" ", 1)
        except ValueError:
            raise NotAuthorizedException(detail="Invalid 'Authorization' schema. Shound be 'Bearer <token>'")

        lc_scheme = auth_scheme.lower()

        if raw_token is None:
            raise NotAuthorizedException(detail="No 'Bearer' token provided")

        if lc_scheme != "bearer":
            raise NotAuthorizedException(detail=f"Invalid 'Authorization' scheme: {auth_scheme}")
        
        return await self.attempt_jwt_authentication(raw_token)


if __name__ == "__main__":
    print(JWToken.encode_token({"name": "Slack Integration"}))
