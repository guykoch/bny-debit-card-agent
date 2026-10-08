"""
Errors we return to the advisor. Each one has a short code so the chat layer
(or a future agent loop) can react without parsing English.

Rule: never explain WHY an entitlement failed. Saying "that client belongs to
another advisor" leaks the existence of the client.
"""


class AgentError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class NotEntitled(AgentError):
    def __init__(self, message: str = "You do not have permission to perform that action on this account."):
        super().__init__("not_entitled", message)


class BadRequest(AgentError):
    def __init__(self, message: str):
        super().__init__("bad_request", message)


class NotPossible(AgentError):
    """The action is understood and allowed, but the card's state forbids it."""
    def __init__(self, code: str, message: str):
        super().__init__(code, message)


class UpstreamUnavailable(AgentError):
    def __init__(self, message: str = "The card system is not responding. Nothing has been changed."):
        super().__init__("api_unavailable", message)
