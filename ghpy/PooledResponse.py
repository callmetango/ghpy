from __future__ import annotations

from http.client import HTTPResponse, HTTPSConnection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from .Connections import Connections


class PooledResponse:
	def __init__(self, response: HTTPResponse, connections: Connections,
			connection: HTTPSConnection):
		self.response = response
		self.connections = connections
		self.connection = connection

	def __enter__(self) -> "PooledResponse":
		return self

	def __exit__(self, excType, excValue, traceback) -> None:
		self.close()

	def close(self) -> None:
		if not self.connection:
			return
		try:
			self.response.read()
			self.response.close()
		finally:
			self.connections.takeBack(self.connection)
			self.connection = None

	def read(self, amount: int = -1) -> bytes:
		return self.response.read(amount)

	def getheader(self, name: str, default: str | None = None) -> str | None:
		return self.response.getheader(name, default)

	@property
	def headers(self):
		return self.response.headers

	@property
	def reason(self) -> str:
		return self.response.reason

	@property
	def status(self) -> int:
		return self.response.status
