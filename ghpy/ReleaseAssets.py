import json
import logging
import time

from typing import Any, Iterator

from fnmatch import fnmatch
from .errors.AssetTimeoutError import AssetTimeoutError
from .RequestFactory import RequestFactory

PAGE_SIZE = 100
MAX_ASSETS = 1000
MAX_PAGES = MAX_ASSETS // PAGE_SIZE

RELEASE_ASSETS_URL = "https://api.github.com/repos/{owner}/{repo}/releases/{id}/assets"
RELEASE_ASSET_URL = "https://api.github.com/repos/{owner}/{repo}/releases/assets/{id}"

logger = logging.getLogger(__name__)


class ReleaseAssets:
	def __init__(self, requests: RequestFactory, token: str, owner: str, repo: str,
			releaseId: int):
		self.owner = owner
		self.repo = repo
		self.releaseId = releaseId
		self.token = token
		self.requests = requests

	def find(self, patterns: list[str]) -> dict[str, Any]:
		assets: dict[str, Any] = {}
		headers = {
			"Authorization": f"Bearer {self.token}",
			"Accept": "application/vnd.github+json",
		}

		for page in range(1, MAX_PAGES + 1):
			url = RELEASE_ASSETS_URL.format(owner=self.owner, repo=self.repo,
					id=self.releaseId) + f"?per_page={PAGE_SIZE}&page={page}"
			with self.requests.get(url, headers=headers) as response:
				pageAssets = json.load(response)
				assets.update({asset["name"]: asset for asset in pageAssets
					if not patterns or any(
						fnmatch(asset["name"], pattern) for pattern in patterns
					)})
			if len(pageAssets) < PAGE_SIZE:
				break

		return assets

	def awaitAssets(self, names: list[str],
			deadline: float) -> Iterator[tuple[str, dict[str, Any]]]:
		pending = set(names)

		for retry in range(self.requests.maxRetries + 1):
			assets = self.find(list(pending))
			for name, asset in assets.items():
				if name not in pending:
					continue
				pending.remove(name)
				yield name, asset
			if not pending:
				return
			if retry >= self.requests.maxRetries or time.monotonic() >= deadline:
				break
			delay = min(self.requests.delay + retry * self.requests.increment,
				self.requests.maxDelay)
			time.sleep(delay)

		raise AssetTimeoutError(list(pending))

	def deleteAsset(self, assetId: int) -> None:
		url = RELEASE_ASSET_URL.format(owner=self.owner, repo=self.repo, id=assetId)
		headers = {
			"Authorization": f"Bearer {self.token}",
			"Accept": "application/vnd.github+json",
		}
		with self.requests.delete(url, headers=headers):
			pass

