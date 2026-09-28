from __future__ import annotations

from .GhpyError import GhpyError


class ReleaseNotFoundError(GhpyError):
	def __init__(self, tag: str):
		self.tag = tag
		super().__init__(f"Release {tag} not found")
