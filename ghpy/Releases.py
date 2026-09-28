import json

from .Release import Release
from .ReleaseAssets import ReleaseAssets
from .RequestFactory import RequestFactory
from .errors.GraphQLError import GraphQLError
from .errors.ReleaseNotFoundError import ReleaseNotFoundError


GET_RELEASE_QUERY = """
query($owner: String!, $repo: String!, $tag: String!) {
	repository(owner: $owner, name: $repo) {
		isPrivate
		release(tagName: $tag) {
			databaseId
			tagName
			isDraft
		}
	}
}
"""


class Releases:
	def __init__(self, token: str, requests: RequestFactory):
		self.token = token
		self.requests = requests

	def getRelease(self, owner: str, repo: str, tag: str) -> Release:
		headers = {
			"Authorization": f"Bearer {self.token}",
			"Content-Type": "application/json",
		}
		data = json.dumps({"query": GET_RELEASE_QUERY,
			"variables": {"owner": owner, "repo": repo, "tag": tag}
		}).encode()

		with self.requests.post("https://api.github.com/graphql", headers=headers,
				data=data) as response:
			body = response.read()
			result = json.loads(body)

		if "errors" in result:
			raise GraphQLError(result)

		repository = result["data"]["repository"]
		releaseData = repository["release"]
		if releaseData is None:
			raise ReleaseNotFoundError(tag)

		releaseData["isPrivate"] = repository["isPrivate"]
		releaseId = releaseData["databaseId"]
		assets = ReleaseAssets(self.requests, self.token, owner, repo, releaseId)
		return Release(owner, repo, releaseData, self.token, self.requests, assets)
