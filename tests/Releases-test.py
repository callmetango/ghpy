import json
import pytest
from unittest.mock import MagicMock, Mock, patch

from ghpy.PooledResponse import PooledResponse
from ghpy.Releases import Releases
from ghpy.errors.GraphQLError import GraphQLError
from ghpy.errors.ReleaseNotFoundError import ReleaseNotFoundError


def Given_a_graphql_response_with_errors():

	ERRORS = [{"message": "Something went wrong"}]
	BODY = json.dumps({"errors": ERRORS}).encode()

	requests = Mock()
	response = Mock(spec=PooledResponse)
	context = MagicMock()

	response.read.return_value = BODY
	context.__enter__.return_value = response
	requests.post.return_value = context

	releases = Releases("token", requests)

	def When_the_release_is_requested():

		with pytest.raises(GraphQLError) as error:
			releases.getRelease("owner", "repo", "v1")

		actual = error.value

		def Then_the_graphql_errors_are_preserved():
			assert actual.response == {"errors": ERRORS}


def Given_a_graphql_response_without_the_release():

	BODY = json.dumps({
		"data": {
			"repository": {
				"isPrivate": False,
				"release": None,
			},
		},
	}).encode()

	requests = Mock()
	response = Mock(spec=PooledResponse)
	context = MagicMock()

	response.read.return_value = BODY
	context.__enter__.return_value = response
	requests.post.return_value = context

	releases = Releases("token", requests)

	def When_the_release_is_requested():

		with pytest.raises(ReleaseNotFoundError) as error:
			releases.getRelease("owner", "repo", "v1")

		actual = error.value

		def Then_the_tag_is_reported():
			assert actual.tag == "v1"


def Given_a_graphql_response_with_a_release():

	BODY = json.dumps({
		"data": {
			"repository": {
				"isPrivate": True,
				"release": {
					"databaseId": 42,
					"tagName": "v1",
					"isDraft": False,
				},
			},
		},
	}).encode()

	requests = Mock()
	response = Mock(spec=PooledResponse)
	context = MagicMock()

	response.read.return_value = BODY
	context.__enter__.return_value = response
	requests.post.return_value = context

	releases = Releases("token", requests)

	def When_the_release_is_requested():

		with patch("ghpy.Releases.ReleaseAssets") as releaseAssets:
			with patch("ghpy.Releases.Release") as release:
				actual = releases.getRelease("owner", "repo", "v1")

		def Then_the_release_is_created():
			release.assert_called_once()

		def Then_the_release_visibility_is_preserved():
			data = release.call_args.args[2]
			assert data["isPrivate"] is True

		def Then_the_release_assets_are_created():
			releaseAssets.assert_called_once_with(
				requests,
				"token",
				"owner",
				"repo",
				42,
			)

		def Then_the_assets_are_attached_to_the_release():
			assets = releaseAssets.return_value
			assert release.call_args.args[5] is assets
