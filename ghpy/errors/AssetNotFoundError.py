from .GhpyError import GhpyError


class AssetNotFoundError(GhpyError):
	def __init__(self, patterns: list[str]):
		self.patterns = patterns
		super().__init__(f"No assets found for: {', '.join(patterns)}")
