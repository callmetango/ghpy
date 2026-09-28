import json

import pytest
from unittest.mock import MagicMock, Mock, patch

from ghpy.PooledResponse import PooledResponse
from ghpy.ReleaseAssets import ReleaseAssets, PAGE_SIZE, MAX_PAGES
from ghpy.RequestFactory import RequestFactory
from ghpy.errors.AssetTimeoutError import AssetTimeoutError


def Given_a_page_with_matching_and_non_matching_assets():

	MATCH = {"name": "package.pkg"}
	OTHER = {"name": "README.txt"}
	ASSETS = [MATCH, OTHER]

	requests = Mock(spec=RequestFactory)
	response = MagicMock(spec=PooledResponse)
	requests.get.return_value = response

	releaseAssets = ReleaseAssets( requests, "token", "owner", "repo", 1)

	def When_assets_are_found():

		with patch("ghpy.ReleaseAssets.json.load", return_value=ASSETS):
			actual = releaseAssets.find(["*.pkg"])

		def Then_only_matching_assets_are_returned():
			assert actual == {"package.pkg": MATCH}


def Given_a_page_with_multiple_assets():

	ASSET_ONE = {"name": "one.pkg"}
	ASSET_TWO = {"name": "two.pkg"}
	ASSETS = [ASSET_ONE, ASSET_TWO]

	requests = Mock(spec=RequestFactory)
	response = MagicMock(spec=PooledResponse)
	requests.get.return_value = response

	releaseAssets = ReleaseAssets( requests, "token", "owner", "repo", 1)

	def When_all_assets_are_requested():

		with patch("ghpy.ReleaseAssets.json.load", return_value=ASSETS):
			actual = releaseAssets.find([])

		def Then_all_assets_are_returned():
			assert actual == {
				"one.pkg": ASSET_ONE,
				"two.pkg": ASSET_TWO,
			}

def Given_a_full_first_page():

	FIRST_PAGE = [{"name": f"one-{number}.pkg"} for number in range(PAGE_SIZE)]
	SECOND_PAGE = [{"name": "last.pkg"}]

	requests = Mock(spec=RequestFactory)
	response = MagicMock(spec=PooledResponse)
	requests.get.return_value = response

	releaseAssets = ReleaseAssets( requests, "token", "owner", "repo", 1)

	def When_assets_are_found():

		with patch(
			"ghpy.ReleaseAssets.json.load",
			side_effect=[FIRST_PAGE, SECOND_PAGE],
		):
			actual = releaseAssets.find([])

		def Then_the_next_page_is_requested():
			assert requests.get.call_count == 2

		def Then_assets_from_both_pages_are_returned():
			assert len(actual) == PAGE_SIZE + 1
			assert "last.pkg" in actual


def Given_a_short_first_page():

	ASSETS = [{"name": "one.pkg"}]

	requests = Mock(spec=RequestFactory)
	response = MagicMock(spec=PooledResponse)
	requests.get.return_value = response

	releaseAssets = ReleaseAssets( requests, "token", "owner", "repo", 1)

	def When_assets_are_found():

		with patch("ghpy.ReleaseAssets.json.load", return_value=ASSETS):
			releaseAssets.find([])

		def Then_no_second_page_is_requested():
			requests.get.assert_called_once()


def Given_every_page_is_full():

	ASSETS = [{"name": f"asset-{number}.pkg"} for number in range(PAGE_SIZE)]

	requests = Mock(spec=RequestFactory)
	response = MagicMock(spec=PooledResponse)
	requests.get.return_value = response

	releaseAssets = ReleaseAssets( requests, "token", "owner", "repo", 1)

	def When_assets_are_found():

		with patch("ghpy.ReleaseAssets.json.load", return_value=ASSETS):
			releaseAssets.find([])

		def Then_the_page_limit_is_respected():
			assert requests.get.call_count == MAX_PAGES


def Given_an_asset_that_is_immediately_available():

	ASSET_NAME = "package.pkg"
	ASSET = {"name": ASSET_NAME}
	NAMES = [ASSET_NAME]
	DEADLINE = 100

	requests = Mock(spec=RequestFactory)
	requests.maxRetries = 3
	requests.delay = 1
	requests.increment = 1
	requests.maxDelay = 10
	assets = ReleaseAssets(requests, "token", "owner", "repo", 1)

	def When_assets_are_awaited():

		assets.find = Mock(return_value={ASSET_NAME: ASSET})

		with patch("ghpy.ReleaseAssets.time.sleep") as sleep:
			actual = list(assets.awaitAssets(NAMES, DEADLINE))

		def Then_the_asset_is_returned():
			assert actual == [(ASSET_NAME, ASSET)]

		def Then_no_retry_is_performed():
			sleep.assert_not_called()


def Given_an_asset_that_appears_after_polling():

	ASSET_NAME = "package.pkg"
	ASSET = {"name": ASSET_NAME}
	NAMES = [ASSET_NAME]
	DEADLINE = 100
	DELAY = 2

	requests = Mock(spec=RequestFactory)
	requests.maxRetries = 3
	requests.delay = DELAY
	requests.increment = 1
	requests.maxDelay = 10
	assets = ReleaseAssets(requests, "token", "owner", "repo", 1)

	assets.find = Mock(side_effect=[{}, {ASSET_NAME: ASSET}])

	def When_assets_are_awaited():

		with patch("ghpy.ReleaseAssets.time.monotonic", return_value=0):
			with patch("ghpy.ReleaseAssets.time.sleep") as sleep:
				actual = list(assets.awaitAssets(NAMES, DEADLINE))

		def Then_the_asset_is_returned():
			assert actual == [(ASSET_NAME, ASSET)]

		def Then_one_retry_delay_is_used():
			sleep.assert_called_once_with(DELAY)


def Given_assets_appear_across_multiple_polls():

	ASSET_ONE = ("one.pkg", {"name": "one.pkg"})
	ASSET_TWO = ("two.pkg", {"name": "two.pkg"})
	NAMES = ["one.pkg", "two.pkg"]
	DEADLINE = 100

	requests = Mock(spec=RequestFactory)
	requests.maxRetries = 3
	requests.delay = 1
	requests.increment = 1
	requests.maxDelay = 10
	assets = ReleaseAssets(requests, "token", "owner", "repo", 1)

	assets.find = Mock(side_effect=[
		{ASSET_ONE[0]: ASSET_ONE[1]},
		{ASSET_ONE[0]: ASSET_ONE[1], ASSET_TWO[0]: ASSET_TWO[1]},
	])

	def When_assets_are_awaited():

		with patch("ghpy.ReleaseAssets.time.monotonic", return_value=0):
			with patch("ghpy.ReleaseAssets.time.sleep") as sleep:
				actual = list(assets.awaitAssets(NAMES, DEADLINE))

		def Then_each_asset_is_returned_once():
			assert actual == [ASSET_ONE, ASSET_TWO]

		def Then_one_retry_is_performed():
			sleep.assert_called_once_with(1)


def Given_assets_that_never_appear():

	NAMES = ["one.pkg", "two.pkg"]
	MAX_RETRIES = 2
	DEADLINE = 100

	requests = Mock(spec=RequestFactory)
	requests.maxRetries = MAX_RETRIES
	requests.delay = 1
	requests.increment = 1
	requests.maxDelay = 10
	assets = ReleaseAssets(requests, "token", "owner", "repo", 1)

	assets.find = Mock(return_value={})

	def When_assets_are_awaited():

		with patch("ghpy.ReleaseAssets.time.monotonic", return_value=0):
			with patch("ghpy.ReleaseAssets.time.sleep"):
				with pytest.raises(AssetTimeoutError) as error:
					list(assets.awaitAssets(NAMES, DEADLINE))

		actual = error.value

		def Then_the_remaining_assets_are_reported():
			assert set(actual.names) == set(NAMES)

		def Then_the_maximum_number_of_polls_is_used():
			assert assets.find.call_count == MAX_RETRIES + 1


def Given_the_asset_deadline_expires():

	NAMES = ["package.pkg"]
	DEADLINE = 10

	requests = Mock(spec=RequestFactory)
	requests.maxRetries = 3
	requests.delay = 1
	requests.increment = 1
	requests.maxDelay = 10
	assets = ReleaseAssets(requests, "token", "owner", "repo", 1)

	assets.find = Mock(return_value={})

	def When_assets_are_awaited():

		with patch("ghpy.ReleaseAssets.time.monotonic", return_value=10):
			with patch("ghpy.ReleaseAssets.time.sleep") as sleep:
				with pytest.raises(AssetTimeoutError):
					list(assets.awaitAssets(NAMES, DEADLINE))

		def Then_no_retry_is_started():
			assets.find.assert_called_once()

			sleep.assert_not_called()


def Given_an_asset_with_capped_retry_delay():

	NAMES = ["package.pkg"]
	MAX_RETRIES = 3
	DELAY = 2
	INCREMENT = 3
	MAX_DELAY = 4
	DEADLINE = 100

	requests = Mock(spec=RequestFactory)
	requests.maxRetries = MAX_RETRIES
	requests.delay = DELAY
	requests.increment = INCREMENT
	requests.maxDelay = MAX_DELAY
	assets = ReleaseAssets(requests, "token", "owner", "repo", 1)

	assets.find = Mock(return_value={})

	def When_assets_are_awaited():

		with patch("ghpy.ReleaseAssets.time.monotonic", return_value=0):
			with patch("ghpy.ReleaseAssets.time.sleep") as sleep:
				with pytest.raises(AssetTimeoutError):
					list(assets.awaitAssets(NAMES, DEADLINE))

		def Then_retry_delays_are_capped():
			assert sleep.call_args_list == [
				((2,),),
				((4,),),
				((4,),),
			]


def Given_an_asset_to_delete():

	ASSET_ID = 42

	requests = Mock(spec=RequestFactory)
	response = MagicMock(spec=PooledResponse)
	requests.delete.return_value = response
	assets = ReleaseAssets(requests, "token", "owner", "repo", 1)

	def When_the_asset_is_deleted():

		assets.deleteAsset(ASSET_ID)

		def Then_the_delete_request_is_made():
			requests.delete.assert_called_once_with(
				"https://api.github.com/repos/owner/repo/releases/assets/42",
				headers={
					"Authorization": "Bearer token",
					"Accept": "application/vnd.github+json",
				},
			)

		def Then_the_response_is_closed():
			response.__exit__.assert_called_once()
