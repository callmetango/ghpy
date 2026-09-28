from __future__ import annotations

from http.client import HTTPSConnection
from queue import Empty, LifoQueue
from threading import Semaphore
from typing import TYPE_CHECKING, BinaryIO

from .PooledResponse import PooledResponse


MAX_CONNECTIONS = 4


class Connections:
	def __init__(self, host: str, maxConnections: int = MAX_CONNECTIONS):
		self.host = host
		self.connections: LifoQueue[HTTPSConnection] = LifoQueue()
		self.semaphore = Semaphore(maxConnections)

	def request(self, method: str, url: str, headers: dict[str, str],
			data: bytes | BinaryIO | None) -> PooledResponse:
		connection = self._acquire()
		try:
			connection.request(method, url, headers=headers, body=data)
			response = connection.getresponse()
		except OSError:
			self._close(connection)
			raise
		return PooledResponse(response, self, connection)

	def takeBack(self, connection: HTTPSConnection) -> None:
		self.connections.put(connection)
		self.semaphore.release()

	def _acquire(self) -> HTTPSConnection:
		self.semaphore.acquire()
		try:
			return self.connections.get_nowait()
		except Empty:
			return HTTPSConnection(self.host)

	def _close(self, connection: HTTPSConnection) -> None:
		connection.close()
		self.semaphore.release()
