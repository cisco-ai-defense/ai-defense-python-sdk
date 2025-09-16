from requests.auth import AuthBase


class ManagementAuth(AuthBase):
    """
    Authentication handler for the AI Defense Management API.

    This class implements the AuthBase interface from requests to provide
    authentication for the AI Defense Management API.

    Args:
        api_key (str): The API key for the Management API.
    """

    def __init__(self, api_key: str):
        """
        Initialize the ManagementAuth.

        Args:
            api_key (str): The API key for the Management API.
        """
        self.api_key = api_key

    def __call__(self, r):
        """
        Add authentication headers to the request.

        Args:
            r (requests.Request): The request to authenticate.

        Returns:
            requests.Request: The authenticated request.
        """
        r.headers["X-Cisco-AI-Defense-Tenant-API-Key"] = self.api_key
        return r

    def validate(self):
        """Validate the API key format."""
        if not self.token or not isinstance(self.token, str) or len(self.token) != 64:
            raise ValueError("Invalid API key format")
        return True
