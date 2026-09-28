from .GhpyError import GhpyError


class DownloadError(Exception):
	def __init__(self, name: str, status: int):
		self.name = name
		self.status = status
		super().__init__(f"Failed to download {name} (HTTP {status})")
