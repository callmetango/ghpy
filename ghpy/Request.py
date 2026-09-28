from __future__ import annotations

import socket
import time

from typing import TYPE_CHECKING
from urllib.parse import urljoin

from .PooledResponse import PooledResponse
from .errors.HTTPError import HTTPError
from .errors.InvalidRedirectError import InvalidRedirectError
from .errors.TooManyRedirectsError import TooManyRedirectsError
from .netlib import sameOrigin, stripHeaders

from typing import BinaryIO

if TYPE_CHECKING:
	from RequestFactory import RequestFactory


MAX_CONNECTION_ERRORS = 3
MAX_DELAY = 300
MAX_REDIRECTS = 5
MAX_RETRIES = 8
RETRY_DELAY = 1
RETRY_INCREMENT = 1

REDIRECT_PRESERVE_METHOD = {307, 308}
REDIRECT_TO_GET = {301, 302, 303}
REDIRECT_STATUSES = REDIRECT_PRESERVE_METHOD | REDIRECT_TO_GET
RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}

SENSITIVE_HEADERS = {"authorization", "proxy-authorization"}


class Request:
	def __init__(self, requests: RequestFactory, method: str, url: str,
			headers: dict[str, str], data: bytes | BinaryIO | None, timeout: int = 30,
			maxRetries: int = MAX_RETRIES, delay: int = RETRY_DELAY,
			increment: int = RETRY_INCREMENT, maxDelay: int = MAX_DELAY,
			retryStatuses: set[int] | None = None):
		self.requests = requests
		self.method = method
		self.url = url
		self.headers = headers
		self.data = data
		self.timeout = timeout
		self.maxRetries = maxRetries
		self.delay = delay
		self.increment = increment
		self.maxDelay = maxDelay
		self.retryStatuses = RETRY_STATUSES | (retryStatuses or set())

		self.retry = 0
		self.connectionErrors = 0
		self.redirects = 0
		self.spent = 0

	def execute(self) -> PooledResponse:
		while True:
			try:
				connections = self.requests.getConnections(self.url)
				if hasattr(self.data, "seek"):
					self.data.seek(0)
				response = connections.request(self.method, self.url,
						self.headers, self.data)
				self.connectionErrors = 0
				if self._redirect(response):
					continue
				if not self._shouldRetry(response):
					if response.status >= 400:
						raise self._httpError(response)
					return response
				response.close()
				self._wait(response.headers)
			except OSError as error:
				self.connectionErrors += 1
				if not self._couldRetry(error):
					raise
				self._wait()

	def _redirect(self, response: PooledResponse):
		if response.status not in REDIRECT_STATUSES:
			return False
		response.close()

		location = response.headers.get("Location")
		if not location:
			raise InvalidRedirectError(self.url, response.status, response.reason)
		if self.redirects >= MAX_REDIRECTS:
			raise TooManyRedirectsError(self.url, response.status, response.reason)

		url = self.url
		self.url = urljoin(self.url, location)
		if not sameOrigin(url, self.url):
			self.headers = stripHeaders(self.headers, SENSITIVE_HEADERS)
		if response.status in REDIRECT_TO_GET:
			self.method = "GET"
			self.headers.pop("Content-Length", None)
			self.headers.pop("Content-Type", None)
			self.data = None
		self.redirects += 1
		return True

	def _shouldRetry(self, response: PooledResponse):
		return response.status in self.retryStatuses or (
			response.status == 403 and (
				response.headers.get("Retry-After") or
				response.headers.get("X-RateLimit-Remaining") == "0"
			)
		)

	def _couldRetry(self, error: OSError):
		return isinstance(error, (BrokenPipeError, ConnectionRefusedError,
			ConnectionResetError, socket.gaierror)) and \
			self.connectionErrors < MAX_CONNECTION_ERRORS

	def _wait(self, headers: dict[str, str] | None = None):
		if self.retry >= self.maxRetries:
			raise TimeoutError(f"Timed out after {self.retry} retries")

		delay = min(self.delay + self.retry * self.increment, self.maxDelay)
		if headers:
			delay = max(delay, int(headers.get("Retry-After", "0")))
			if headers.get("X-RateLimit-Remaining") == "0":
				reset = int(headers.get("X-RateLimit-Reset", "0"))
				delay = max(delay, reset - int(time.time()))

		if self.spent + delay > self.timeout:
			raise TimeoutError(f"Timed out after {self.retry} retries")

		self.spent += delay
		self.retry += 1
		time.sleep(delay)

	def _httpError(self, response: PooledResponse) -> HTTPError:
		try:
			body = response.read()
			return HTTPError(self.url, response.status, response.reason,
					response.headers, body)
		finally:
			response.close()
