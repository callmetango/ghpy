from http.client import HTTPMessage


class HTTPError(Exception):
	def __init__(self, url: str, status: int, reason: str,
			headers: HTTPMessage, body: bytes):
		self.url = url
		self.status = status
		self.code = status
		self.reason = reason
		self.headers = headers
		self.body = body
		super().__init__(f"HTTP {status} {reason}")
