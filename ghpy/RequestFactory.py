from threading import Lock
from typing import BinaryIO
from urllib.parse import urlsplit

from .Connections import Connections
from .PooledResponse import PooledResponse
from .Request import MAX_DELAY, MAX_RETRIES, RETRY_DELAY, RETRY_INCREMENT, Request

DEFAULT_HEADERS = {"User-Agent": "ghpy"}


class RequestFactory:
	def __init__(self, timeout: int = 30, maxRetries: int = MAX_RETRIES,
			delay: int = RETRY_DELAY, increment: int = RETRY_INCREMENT,
			maxDelay: int = MAX_DELAY):
		self.timeout = timeout
		self.maxRetries = maxRetries
		self.delay = delay
		self.increment = increment
		self.maxDelay = maxDelay
		self.connections: dict[str, Connections] = {}
		self.connectionsLock = Lock()

	def get(self, url: str, headers: dict[str, str] | None = None,
			retryStatuses: set[int] | None = None,
			timeout: int | None = None) -> PooledResponse:
		return self._request("GET", url, headers, retryStatuses=retryStatuses,
				timeout=timeout)

	def post(self, url: str, headers: dict[str, str] | None = None,
			data: bytes | BinaryIO | None = None,
			retryStatuses: set[int] | None = None) -> PooledResponse:
		return self._request("POST", url, headers, data, retryStatuses)

	def delete(self, url: str, headers: dict[str, str] | None = None,
			retryStatuses: set[int] | None = None) -> PooledResponse:
		return self._request("DELETE", url, headers, retryStatuses=retryStatuses)

	def _request(self, method: str, url: str, headers: dict[str, str] | None = None,
			data: bytes | BinaryIO | None = None, retryStatuses: set[int] | None = None,
			timeout: int | None = None) -> PooledResponse:
		requestHeaders = {**DEFAULT_HEADERS, **(headers or {})}
		return Request(self, method, url, requestHeaders, data,
				self.timeout if timeout is None else timeout,
				self.maxRetries, self.delay, self.increment, self.maxDelay,
				retryStatuses).execute()

	def getConnections(self, url: str) -> Connections:
		host = urlsplit(url).netloc
		with self.connectionsLock:
			if host not in self.connections:
				self.connections[host] = Connections(host)
			return self.connections[host]
