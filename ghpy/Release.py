import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar
from urllib.parse import quote

from .ReleaseAssets import ReleaseAssets
from .RequestFactory import RequestFactory
from .errors.AssetNotFoundError import AssetNotFoundError
from .errors.AssetTimeoutError import AssetTimeoutError
from .errors.DownloadError import DownloadError
from .errors.HTTPError import HTTPError
from .errors.OperationError import OperationError
from .errors.UploadError import UploadError


RELEASE_ASSET_URL = "https://api.github.com/repos/{owner}/{repo}/releases/assets/{id}"
RELEASE_UPLOAD_URL = "https://uploads.github.com/repos/{owner}/{repo}/releases/{id}/assets"
MAX_WORKERS = 4

T = TypeVar("T")

logger = logging.getLogger(__name__)


def parallel(items: Iterable[T], function: Callable[[T], None]) -> None:
	failed = False
	with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
		futures = [executor.submit(function, item) for item in items]
		for future in as_completed(futures):
			if error := future.exception():
				logger.error("%s", error)
				failed = True
	if failed:
		raise OperationError("Operation failed")


class Release:
	def __init__(self, owner: str, repo: str, data: dict[str, Any], token: str,
			requests: RequestFactory, assets: ReleaseAssets):
		self.owner = owner
		self.repo = repo
		self.id = data["databaseId"]
		self.tag = data["tagName"]
		self.isDraft = data["isDraft"]
		self.isPrivate = data["isPrivate"]
		self.token = token
		self.requests = requests
		self.assets = assets

	def uploadAssets(self, files: list[Path], clobber: bool = False) -> None:
		names = [path.name for path in files]
		if len(names) != len(set(names)):
			raise ValueError("Upload files must have unique names")

		assets = self.assets.find([]) if clobber else {}
		parallel(files, lambda path: self.uploadAsset(path, assets.get(path.name)))

	def uploadAsset(self, path: Path, asset: dict[str, Any] | None = None) -> None:
		if asset is not None:
			self.assets.deleteAsset(asset["id"])

		url = RELEASE_UPLOAD_URL.format(owner=self.owner, repo=self.repo, id=self.id)
		url += f"?name={quote(path.name)}"

		file = response = None
		try:
			file = path.open("rb")
			headers = {
				"Authorization": f"Bearer {self.token}",
				"Accept": "application/vnd.github+json",
				"Content-Type": "application/octet-stream",
				"Content-Length": str(path.stat().st_size),
			}
			response = self.requests.post(url, headers=headers, data=file)
		except HTTPError as error:
			raise UploadError(path.name, error.status) from error
		finally:
			file and file.close()
			response and response.close()

		logger.info("Uploaded %s", path.name)

	def downloadAssets(self, patterns: list[str]) -> None:
		assets = self.assets.find(patterns)
		if not assets:
			raise AssetNotFoundError(patterns)

		parallel(assets.items(), self.downloadAsset)

	def downloadAsset(self, asset: tuple[str, dict[str, Any]]) -> None:
		name, data = asset
		url = (
			RELEASE_ASSET_URL.format(owner=self.owner, repo=self.repo, id=data["id"])
			if self.isPrivate
			else data["browser_download_url"]
		)
		headers = {
			"Authorization": f"Bearer {self.token}",
			"Accept": "application/octet-stream"
		}

		file = response = None
		try:
			response = self.requests.get(url, headers=headers)
			file = Path(name).open("wb")
			while chunk := response.read(1024 * 1024):
				file.write(chunk)
		except HTTPError as error:
			raise DownloadError(name, error.status) from error
		finally:
			file and file.close()
			response and response.close()

		logger.info("Downloaded %s", name)

	def awaitAssets(self, names: list[str]) -> None:
		deadline = time.monotonic() + self.requests.timeout
		parallel(self.assets.awaitAssets(names, deadline),
				lambda asset: self.awaitAsset(asset, deadline))

	def awaitAsset(self, asset: tuple[str, dict[str, Any]],
			deadline: float) -> None:
		name, data = asset
		logger.info("Waiting for %s", name)
		url = (
			RELEASE_ASSET_URL.format(owner=self.owner, repo=self.repo, id=data["id"])
			if self.isPrivate else data["browser_download_url"]
		)
		headers = {
			"Authorization": f"Bearer {self.token}",
			"Accept": "application/octet-stream",
		}
		remaining = math.ceil(deadline - time.monotonic())
		if remaining <= 0:
			raise AssetTimeoutError(name)

		response = None
		try:
			response = self.requests.get(url, headers=headers, retryStatuses={404},
					timeout=remaining)
		except TimeoutError as error:
			raise AssetTimeoutError(name) from error
		finally:
			response and response.close()

		logger.info("Available %s", name)
