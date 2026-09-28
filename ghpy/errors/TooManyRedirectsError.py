from .RedirectError import RedirectError


class TooManyRedirectsError(RedirectError):
	def __init__(self, url: str, status: int, reason: str):
		super().__init__(url, status, reason, "Too many redirects")
