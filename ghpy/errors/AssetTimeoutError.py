from .GhpyError import GhpyError


class AssetTimeoutError(GhpyError):
	def __init__(self, names: str | list[str], status: int = 0):
		if isinstance(names, str):
			names = [names]
		self.names = names
		message = "Timed out waiting for assets"
		if status:
			message += f" (HTTP {status})"
		super().__init__(f"{message}: {', '.join(names)}")
