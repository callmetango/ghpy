from .GhpyError import GhpyError


class RedirectError(GhpyError):
	def __init__(self, url: str, status: int, reason: str, message: str):
		self.url = url
		self.status = status
		self.reason = reason
		super().__init__(message)
