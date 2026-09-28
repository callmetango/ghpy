from __future__ import annotations

from .GhpyError import GhpyError


class GraphQLError(GhpyError):
	def __init__(self, response: dict):
		self.response = response
		messages = [error["message"] for error in response["errors"]]
		super().__init__(", ".join(messages))
