"""Create a Firebase ID token for local development testing only."""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from firebase_admin import auth

from app.auth.firebase import get_firebase_app
from app.core.config import settings


def exchange_custom_token(custom_token: str) -> str:
    if not settings.firebase_web_api_key:
        raise RuntimeError("FIREBASE_WEB_API_KEY must be configured in .env.")

    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
        f"?key={settings.firebase_web_api_key.get_secret_value()}"
    )
    payload = json.dumps(
        {"token": custom_token, "returnSecureToken": True}
    ).encode()
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            body = json.loads(response.read())
    except HTTPError as error:
        raise RuntimeError("Firebase rejected the custom token exchange.") from error
    except URLError as error:
        raise RuntimeError("Could not reach Firebase Authentication.") from error

    id_token = body.get("idToken")
    if not isinstance(id_token, str) or not id_token:
        raise RuntimeError("Firebase did not return an ID token.")

    return id_token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a Firebase ID token for local API testing."
    )
    parser.add_argument("uid", help="Firebase user UID to impersonate locally")
    args = parser.parse_args()

    if settings.app_env.lower() != "development":
        parser.error("This helper can only run when APP_ENV is development.")

    if not settings.firebase_service_account_path:
        parser.error(
            "FIREBASE_SERVICE_ACCOUNT_PATH must point to a local "
            "service-account JSON file."
        )

    if not Path(settings.firebase_service_account_path).is_file():
        parser.error(
            "FIREBASE_SERVICE_ACCOUNT_PATH does not point to an existing file."
        )

    custom_token = auth.create_custom_token(args.uid, app=get_firebase_app()).decode()
    print(exchange_custom_token(custom_token))


if __name__ == "__main__":
    main()
