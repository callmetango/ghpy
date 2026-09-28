import pytest

from io import BytesIO
from unittest.mock import Mock, patch

from ghpy.PooledResponse import PooledResponse
from ghpy.Release import Release, parallel
from ghpy.ReleaseAssets import ReleaseAssets
from ghpy.RequestFactory import RequestFactory
from ghpy.errors.AssetNotFoundError import AssetNotFoundError
from ghpy.errors.AssetTimeoutError import AssetTimeoutError
from ghpy.errors.DownloadError import DownloadError
from ghpy.errors.HTTPError import HTTPError
from ghpy.errors.OperationError import OperationError
from ghpy.errors.UploadError import UploadError


def Given_a_release_with_a_timeout():

	ASSET_NAME = "file.pkg"
	ASSET = {"name": ASSET_NAME}
	TIMEOUT = 10

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_asset_listing_consumes_part_of_the_timeout():

		requests.timeout = TIMEOUT
		assets.awaitAssets.return_value = iter([(ASSET_NAME, ASSET)])

		with patch("ghpy.Release.time.monotonic", side_effect=[0, 4]):
			with patch.object(release, "awaitAsset") as awaitAsset:
				release.awaitAssets([ASSET_NAME])

		def Then_the_same_deadline_is_passed_to_the_asset():
			awaitAsset.assert_called_once_with((ASSET_NAME, ASSET), TIMEOUT)


def Given_an_upload_that_returns_an_http_error():

	ASSET_NAME = "file.pkg"
	STATUS = 422
	BODY = b"failure"
	URL = "https://uploads.github.com/upload"

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	path = Mock()
	file = BytesIO(BODY)

	path.name = ASSET_NAME
	path.stat.return_value.st_size = len(BODY)
	path.open.return_value = file

	error = HTTPError(URL, STATUS, "Unprocessable Entity", {}, BODY)

	requests.post.side_effect = error

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_uploaded():

		with pytest.raises(UploadError) as exception:
			release.uploadAsset(path)

		actual = exception.value

		def Then_the_http_error_is_translated():
			assert actual.name == ASSET_NAME
			assert actual.status == STATUS
			assert actual.__cause__ is error


def Given_a_successful_upload():

	ASSET_NAME = "file.pkg"
	STATUS = 201
	BODY = b"payload"

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	path = Mock()
	file = BytesIO(BODY)
	response = Mock()

	path.name = ASSET_NAME
	path.stat.return_value.st_size = len(BODY)
	path.open.return_value = file

	response.status = STATUS
	requests.post.return_value = response

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_uploaded():

		release.uploadAsset(path)

		def Then_the_file_and_response_are_closed():
			assert file.closed
			response.close.assert_called_once()


def Given_a_download_that_returns_an_http_error():

	ASSET_NAME = "file.pkg"
	STATUS = 404
	BODY = b"failure"
	URL = "https://api.github.com/repos/owner/repo/releases/assets/1"

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)

	error = HTTPError(URL, STATUS, "Not Found", {}, BODY)

	requests.get.side_effect = error

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_downloaded():

		with pytest.raises(DownloadError) as exception:
			release.downloadAsset((ASSET_NAME, {"id": 1}))

		actual = exception.value

		def Then_the_http_error_is_translated():
			assert actual.name == ASSET_NAME
			assert actual.status == STATUS
			assert actual.__cause__ is error


def Given_a_successful_download():

	ASSET_NAME = "file.pkg"
	STATUS = 200
	BODY = b"payload"
	URL = "https://api.github.com/repos/owner/repo/releases/assets/1"

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	response = Mock(spec=PooledResponse)
	file = BytesIO()

	response.status = STATUS
	response.read.side_effect = [BODY, b""]
	requests.get.return_value = response

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_downloaded():

		with patch("ghpy.Release.Path.open", return_value=file):
			release.downloadAsset((ASSET_NAME, {"id": 1}))

		def Then_the_file_and_response_are_closed():
			assert file.closed
			response.close.assert_called_once()


def Given_a_private_release_asset():

	ASSET_NAME = "file.pkg"
	ASSET_ID = 42
	STATUS = 200
	BODY = b"payload"
	EXPECTED_URL = (
		"https://api.github.com/repos/owner/repo/releases/assets/42"
	)

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	response = Mock(spec=PooledResponse)
	file = BytesIO()

	response.status = STATUS
	response.read.side_effect = [BODY, b""]
	requests.get.return_value = response

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_private_asset_is_downloaded():

		with patch("ghpy.Release.Path.open", return_value=file):
			release.downloadAsset((ASSET_NAME, {"id": ASSET_ID}))

		def Then_the_api_asset_url_is_used():
			requests.get.assert_called_once_with(
				EXPECTED_URL,
				headers={
					"Authorization": "Bearer token",
					"Accept": "application/octet-stream",
				},
			)


def Given_a_public_release_asset():

	ASSET_NAME = "file.pkg"
	ASSET_ID = 42
	STATUS = 200
	BODY = b"payload"
	BROWSER_DOWNLOAD_URL = "https://github.com/owner/repo/releases/download/v1/file.pkg"

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	response = Mock(spec=PooledResponse)
	file = BytesIO()

	response.status = STATUS
	response.read.side_effect = [BODY, b""]
	requests.get.return_value = response

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_public_asset_is_downloaded():

		with patch("ghpy.Release.Path.open", return_value=file):
			release.downloadAsset((
				ASSET_NAME,
				{
					"id": ASSET_ID,
					"browser_download_url": BROWSER_DOWNLOAD_URL,
				},
			))

		def Then_the_browser_download_url_is_used():
			requests.get.assert_called_once_with(
				BROWSER_DOWNLOAD_URL,
				headers={
					"Authorization": "Bearer token",
					"Accept": "application/octet-stream",
				},
			)


def Given_a_download_with_no_matching_assets():

	PATTERNS = ["*.pkg"]

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	assets.find.return_value = {}

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_assets_are_downloaded():

		with pytest.raises(AssetNotFoundError) as error:
			release.downloadAssets(PATTERNS)

		actual = error.value

		def Then_the_missing_assets_are_reported():
			assert actual.patterns == PATTERNS

		def Then_no_download_is_started():
			requests.get.assert_not_called()


def Given_multiple_matching_assets():

	ASSET_ONE = ("one.pkg", {"id": 1})
	ASSET_TWO = ("two.pkg", {"id": 2})
	PATTERNS = ["*.pkg"]

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	assets.find.return_value = dict([ASSET_ONE, ASSET_TWO])

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_assets_are_downloaded():

		with patch.object(release, "downloadAsset") as downloadAsset:
			release.downloadAssets(PATTERNS)

		def Then_all_matching_assets_are_downloaded():
			assert downloadAsset.call_count == 2
			downloadAsset.assert_any_call(ASSET_ONE)
			downloadAsset.assert_any_call(ASSET_TWO)


def Given_upload_files_with_duplicate_names():

	ASSET_NAME = "file.pkg"
	PATHS = [Mock(), Mock()]

	PATHS[0].name = ASSET_NAME
	PATHS[1].name = ASSET_NAME

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_files_are_uploaded():

		with pytest.raises(ValueError) as error:
			release.uploadAssets(PATHS)

		actual = error.value

		def Then_the_duplicate_names_are_rejected():
			assert str(actual) == "Upload files must have unique names"

		def Then_no_upload_is_started():
			requests.post.assert_not_called()


def Given_upload_files_with_clobber():

	ASSET_NAME = "file.pkg"
	EXISTING_ASSET = {"id": 42, "name": ASSET_NAME}
	PATH = Mock()
	PATH.name = ASSET_NAME

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	assets.find.return_value = {ASSET_NAME: EXISTING_ASSET}

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_file_is_uploaded_with_clobber():

		with patch.object(release, "uploadAsset") as uploadAsset:
			release.uploadAssets([PATH], clobber=True)

		def Then_existing_assets_are_found():
			assets.find.assert_called_once_with([])

		def Then_the_existing_asset_is_passed_to_the_upload():
			uploadAsset.assert_called_once_with(PATH, EXISTING_ASSET)


def Given_upload_files_without_clobber():

	ASSET_NAME = "file.pkg"
	PATH = Mock()
	PATH.name = ASSET_NAME

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_file_is_uploaded_without_clobber():

		with patch.object(release, "uploadAsset") as uploadAsset:
			release.uploadAssets([PATH])

		def Then_existing_assets_are_not_found():
			assets.find.assert_not_called()

		def Then_the_file_is_uploaded_without_an_existing_asset():
			uploadAsset.assert_called_once_with(PATH, None)


def Given_multiple_upload_files():

	PATH_ONE = Mock()
	PATH_TWO = Mock()
	PATH_ONE.name = "one.pkg"
	PATH_TWO.name = "two.pkg"

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_files_are_uploaded():

		with patch.object(release, "uploadAsset") as uploadAsset:
			release.uploadAssets([PATH_ONE, PATH_TWO])

		def Then_all_files_are_uploaded():
			assert uploadAsset.call_count == 2
			uploadAsset.assert_any_call(PATH_ONE, None)
			uploadAsset.assert_any_call(PATH_TWO, None)


def Given_assets_become_available():

	ASSET_ONE = ("one.pkg", {"id": 1})
	ASSET_TWO = ("two.pkg", {"id": 2})
	NAMES = ["one.pkg", "two.pkg"]
	TIMEOUT = 10

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	assets.awaitAssets.return_value = iter([ASSET_ONE, ASSET_TWO])
	requests.timeout = TIMEOUT

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": False }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_assets_are_awaited():

		with patch("ghpy.Release.time.monotonic", return_value=0):
			with patch.object(release, "awaitAsset") as awaitAsset:
				release.awaitAssets(NAMES)

		def Then_all_available_assets_are_awaited():
			assert awaitAsset.call_count == 2
			awaitAsset.assert_any_call(ASSET_ONE, TIMEOUT)
			awaitAsset.assert_any_call(ASSET_TWO, TIMEOUT)


def Given_an_asset_that_is_not_yet_available():

	ASSET_NAME = "file.pkg"
	ASSET_ID = 42
	EXPECTED_URL = (
		"https://api.github.com/repos/owner/repo/releases/assets/42"
	)
	REMAINING = 10

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	requests.get.return_value = Mock(spec=PooledResponse)

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_awaited():

		with patch("ghpy.Release.time.monotonic", return_value=0):
			release.awaitAsset((ASSET_NAME, {"id": ASSET_ID}), REMAINING)

		def Then_404_is_a_retryable_status():
			requests.get.assert_called_once_with(
				EXPECTED_URL,
				headers={
					"Authorization": "Bearer token",
					"Accept": "application/octet-stream",
				},
				retryStatuses={404},
				timeout=REMAINING,
			)


def Given_an_asset_with_an_expired_deadline():

	ASSET_NAME = "file.pkg"
	ASSET_ID = 42
	DEADLINE = 10

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_awaited_after_the_deadline():

		with patch("ghpy.Release.time.monotonic", return_value=11):
			with pytest.raises(AssetTimeoutError) as error:
				release.awaitAsset(
					(ASSET_NAME, {"id": ASSET_ID}),
					DEADLINE,
				)

		actual = error.value

		def Then_the_asset_timeout_is_reported():
			assert actual.names == [ASSET_NAME]

		def Then_no_request_is_started():
			requests.get.assert_not_called()


def Given_an_asset_request_that_times_out():

	ASSET_NAME = "file.pkg"
	ASSET_ID = 42
	DEADLINE = 10
	TIMEOUT = TimeoutError("request timed out")

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	requests.get.side_effect = TIMEOUT

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_awaited():

		with patch("ghpy.Release.time.monotonic", return_value=0):
			with pytest.raises(AssetTimeoutError) as error:
				release.awaitAsset(
					(ASSET_NAME, {"id": ASSET_ID}),
					DEADLINE,
				)

		actual = error.value

		def Then_the_timeout_is_translated():
			assert actual.names == [ASSET_NAME]
			assert actual.__cause__ is TIMEOUT


def Given_an_asset_becomes_available():

	ASSET_NAME = "file.pkg"
	ASSET_ID = 42
	DEADLINE = 10

	requests = Mock(spec=RequestFactory)
	assets = Mock(spec=ReleaseAssets)
	response = Mock(spec=PooledResponse)
	requests.get.return_value = response

	data = { "databaseId": 1, "tagName": "v1", "isDraft": False, "isPrivate": True }
	release = Release("owner", "repo", data, "token", requests, assets)

	def When_the_asset_is_awaited():

		with patch("ghpy.Release.time.monotonic", return_value=0):
			release.awaitAsset(
				(ASSET_NAME, {"id": ASSET_ID}),
				DEADLINE,
			)

		def Then_the_response_is_closed():
			response.close.assert_called_once()


def Given_parallel_operations_with_one_failure():

	ITEMS = ["one", "two", "three"]
	FAILED = "two"
	ERROR = ValueError("failed")
	completed = []

	def _perform(item):
		completed.append(item)
		if item == FAILED:
			raise ERROR

	def When_the_operations_are_run():

		with patch("ghpy.Release.logger") as logger:
			with pytest.raises(OperationError):
				parallel(ITEMS, _perform)

		def Then_all_operations_complete():
			assert set(completed) == set(ITEMS)

		def Then_the_worker_error_is_logged():
			logger.error.assert_called_once_with("%s", ERROR)


def Given_parallel_operations_with_multiple_failures():

	ITEMS = ["one", "two", "three"]
	ERROR_ONE = ValueError("one failed")
	ERROR_THREE = RuntimeError("three failed")

	def _perform(item):
		if item == "one":
			raise ERROR_ONE
		if item == "three":
			raise ERROR_THREE

	def When_the_operations_are_run():

		with patch("ghpy.Release.logger") as logger:
			with pytest.raises(OperationError):
				parallel(ITEMS, _perform)

		def Then_every_worker_error_is_logged():
			assert logger.error.call_count == 2

		def Then_the_errors_are_logged():
			logged = {call.args[1] for call in logger.error.call_args_list}
			assert logged == {ERROR_ONE, ERROR_THREE}


def Given_parallel_operations_with_no_failures():

	ITEMS = ["one", "two", "three"]
	completed = []

	def _perform(item):
		completed.append(item)

	def When_the_operations_are_run():

		parallel(ITEMS, _perform)

		def Then_every_operation_completes():
			assert set(completed) == set(ITEMS)
