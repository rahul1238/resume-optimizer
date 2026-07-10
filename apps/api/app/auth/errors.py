class AuthenticationError(Exception):
    status_code = 401
    code = "authentication_error"
    message = "Authentication is required."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class MissingAuthenticationError(AuthenticationError):
    code = "missing_authentication"
    message = "A Firebase ID token is required."


class InvalidAuthenticationError(AuthenticationError):
    code = "invalid_authentication"
    message = "The Firebase ID token is invalid or expired."


class AuthenticationServiceUnavailableError(AuthenticationError):
    status_code = 503
    code = "authentication_service_unavailable"
    message = "Authentication could not be verified. Please try again later."
