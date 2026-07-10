import logging
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, exceptions
from google.auth.exceptions import DefaultCredentialsError

from app.auth.errors import (
    AuthenticationServiceUnavailableError,
    InvalidAuthenticationError,
    MissingAuthenticationError,
)
from app.auth.firebase import get_firebase_app
from app.core.config import settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(
        self,
        uid: str,
        email: str | None,
        email_verified: bool,
    ) -> None:
        self.uid = uid
        self.email = email
        self.email_verified = email_verified


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise MissingAuthenticationError()

    try:
        decoded_token = auth.verify_id_token(
            credentials.credentials,
            app=get_firebase_app(),
            check_revoked=settings.firebase_check_revoked_tokens,
        )
    except (
        auth.ExpiredIdTokenError,
        auth.InvalidIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        ValueError,
    ) as error:
        raise InvalidAuthenticationError() from error
    except (exceptions.FirebaseError, DefaultCredentialsError) as error:
        logger.exception("Firebase ID token verification failed")
        raise AuthenticationServiceUnavailableError() from error

    uid = decoded_token.get("uid")
    if not isinstance(uid, str) or not uid:
        raise InvalidAuthenticationError()

    email = decoded_token.get("email")
    return CurrentUser(
        uid=uid,
        email=email if isinstance(email, str) else None,
        email_verified=decoded_token.get("email_verified") is True,
    )
