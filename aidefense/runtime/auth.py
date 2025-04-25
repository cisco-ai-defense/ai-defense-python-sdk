from requests.auth import AuthBase

auth_header = "X-Cisco-AI-Defense-API-Key"


class RuntimeAuth(AuthBase):
    """Custom authentication class for runtime authentication."""

    def __init__(self, token: str):
        self.token = token
        self.validate()

    def __call__(self, request):
        request.headers[auth_header] = f"{self.token}"
        return request

    def validate(self):
        """Validate the API key format."""
        if not self.token or not isinstance(self.token, str) or len(self.token) != 64:
            raise ValueError("Invalid API key format")
        return True
