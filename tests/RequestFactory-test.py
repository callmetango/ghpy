from io import BytesIO
from unittest.mock import Mock, patch

from ghpy.RequestFactory import RequestFactory


def Given_a_file_upload():

	data = BytesIO(b"package data")
	factory = RequestFactory()

	def When_the_post_request_is_created():

		with patch("ghpy.RequestFactory.Request") as request:
			factory.post("https://example.com/upload", data=data)

		def Then_the_file_is_passed_to_the_request():
			assert request.call_args.args[4] is data
