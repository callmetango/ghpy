from .GhpyError import GhpyError


class UploadError(Exception):
	def __init__(self, name: str, status: int):
		self.name = name
		self.status = status
		super().__init__(f"Failed to upload {name} (HTTP {status})")
