from .RedirectError import RedirectError


class InvalidRedirectError(RedirectError):
	def __init__(self, url: str, status: int, reason: str):
		super().__init__(url, status, reason, "Location header not found")
