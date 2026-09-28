from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from ghpy.PooledResponse import PooledResponse
from ghpy.Request import Request
from ghpy.errors.HTTPError import HTTPError
from ghpy.errors.InvalidRedirectError import InvalidRedirectError
from ghpy.errors.TooManyRedirectsError import TooManyRedirectsError


def Given_a_retryable_http_response():

	RETRY_STATUS = 503
	SUCCESS_STATUS = 200
	URL = "https://example.com/test"
	MAX_RETRIES = 1
	DELAY = 0

	requests = Mock()
	connections = Mock()
	retryResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_the_next_request_succeeds():

		retryResponse.status = RETRY_STATUS
		retryResponse.headers = {}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [retryResponse, successResponse]
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES, delay=DELAY
		)

		actual = request.execute()

		def Then_the_request_is_retried():
			assert connections.request.call_count == 2
			retryResponse.close.assert_called_once()
			assert actual is successResponse
			assert request.retry == MAX_RETRIES


def Given_an_unsuccessful_http_response():

	STATUS = 400
	BODY = b"failure"
	URL = "https://example.com/test"
	MAX_RETRIES = 0

	requests = Mock()
	connections = Mock()
	response = Mock(spec=PooledResponse)

	def When_the_request_is_executed():

		response.status = STATUS
		response.read.return_value = BODY

		connections.request.return_value = response
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES
		)

		with pytest.raises(HTTPError) as error:
			request.execute()

		actual = error.value

		def Then_the_http_error_contains_the_response():
			assert actual.status == STATUS
			assert actual.body == BODY
			response.close.assert_called_once()


def Given_a_request_with_a_stream_body():

	BODY = b"payload"
	URL = "https://example.com/test"
	MAX_RETRIES = 1
	DELAY = 0

	requests = Mock()
	connections = Mock()
	retryResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)
	stream = BytesIO(BODY)

	def When_the_next_request_succeeds():

		retryResponse.status = 503
		retryResponse.headers = {}

		successResponse.status = 200
		successResponse.headers = {}

		positions = []

		def request(method, url, headers, data):
			positions.append(data.tell())
			return retryResponse if len(positions) == 1 else successResponse

		connections.request.side_effect = request
		requests.getConnections.return_value = connections

		request = Request(
			requests, "POST", URL, {}, stream,
			maxRetries=MAX_RETRIES, delay=DELAY
		)

		actual = request.execute()

		def Then_the_stream_is_rewound_for_each_attempt():
			assert positions == [0, 0]
			assert actual is successResponse


def Given_a_connection_error():

	ERROR = ConnectionResetError()
	SUCCESS_STATUS = 200
	URL = "https://example.com/test"
	MAX_RETRIES = 1
	DELAY = 0

	requests = Mock()
	connections = Mock()
	successResponse = Mock(spec=PooledResponse)

	def When_the_next_request_succeeds():

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [ERROR, successResponse]
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES, delay=DELAY
		)

		actual = request.execute()

		def Then_the_request_is_retried():
			assert connections.request.call_count == 2
			assert actual is successResponse
			assert request.connectionErrors == 0


def Given_persistent_connection_errors():

	ERROR = ConnectionResetError()
	URL = "https://example.com/test"
	MAX_RETRIES = 8
	MAX_CONNECTION_ERRORS = 3
	DELAY = 0

	requests = Mock()
	connections = Mock()

	def When_the_request_keeps_failing():

		connections.request.side_effect = ERROR
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES, delay=DELAY
		)

		with pytest.raises(ConnectionResetError) as error:
			request.execute()

		actual = error.value

		def Then_the_connection_error_limit_is_respected():
			assert isinstance(actual, ConnectionResetError)
			assert connections.request.call_count == MAX_CONNECTION_ERRORS
			assert request.connectionErrors == MAX_CONNECTION_ERRORS

def Given_persistent_retryable_http_responses():

	RETRY_STATUS = 503
	URL = "https://example.com/test"
	MAX_RETRIES = 3
	ATTEMPTS = MAX_RETRIES + 1
	DELAY = 0

	requests = Mock()
	connections = Mock()
	response = Mock(spec=PooledResponse)

	def When_the_request_keeps_failing():

		response.status = RETRY_STATUS
		response.headers = {}
		connections.request.return_value = response
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES, delay=DELAY
		)

		with pytest.raises(TimeoutError) as error:
			request.execute()

		actual = error.value

		def Then_the_retry_limit_is_respected():
			assert isinstance(actual, TimeoutError)
			assert connections.request.call_count == ATTEMPTS
			assert response.close.call_count == ATTEMPTS
			assert request.retry == MAX_RETRIES


def Given_a_retryable_response_that_exceeds_the_timeout():

	RETRY_STATUS = 503
	URL = "https://example.com/test"
	TIMEOUT = 1
	DELAY = 2
	ATTEMPTS = 1
	RETRIES = 0
	MAX_RETRIES = 8

	requests = Mock()
	connections = Mock()
	response = Mock(spec=PooledResponse)

	def When_the_retry_delay_exceeds_the_timeout():

		response.status = RETRY_STATUS
		response.headers = {}
		connections.request.return_value = response
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			timeout=TIMEOUT, maxRetries=MAX_RETRIES, delay=DELAY
		)

		with pytest.raises(TimeoutError) as error:
			request.execute()

		actual = error.value

		def Then_the_timeout_is_respected():
			assert isinstance(actual, TimeoutError)
			assert connections.request.call_count == ATTEMPTS
			assert response.close.call_count == ATTEMPTS
			assert request.retry == RETRIES


def Given_a_retryable_response_with_retry_after():

	SUCCESS_STATUS = 200
	RETRY_STATUS = 503
	RETRY_AFTER = 5
	DEFAULT_DELAY = 1
	URL = "https://example.com/test"
	MAX_RETRIES = 1

	requests = Mock()
	connections = Mock()
	retryResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_the_next_request_succeeds():

		retryResponse.status = RETRY_STATUS
		retryResponse.headers = {"Retry-After": str(RETRY_AFTER)}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [retryResponse, successResponse]
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES, delay=DEFAULT_DELAY
		)

		with patch("ghpy.Request.time.sleep") as sleep:
			actual = request.execute()

		def Then_the_retry_after_delay_is_used():
			sleep.assert_called_once_with(RETRY_AFTER)
			assert actual is successResponse
			assert request.spent == RETRY_AFTER
			assert request.retry == MAX_RETRIES


def Given_a_rate_limited_response():

	SUCCESS_STATUS = 200
	RETRY_STATUS = 403
	RATE_LIMIT_REMAINING = "0"
	RATE_LIMIT_RESET = 105
	CURRENT_TIME = 100
	RETRY_DELAY = 1
	URL = "https://example.com/test"
	MAX_RETRIES = 1

	requests = Mock()
	connections = Mock()
	retryResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_the_rate_limit_resets():

		retryResponse.status = RETRY_STATUS
		retryResponse.headers = {
			"X-RateLimit-Remaining": RATE_LIMIT_REMAINING,
			"X-RateLimit-Reset": str(RATE_LIMIT_RESET),
		}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [retryResponse, successResponse]
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES, delay=RETRY_DELAY
		)

		with patch("ghpy.Request.time.time", return_value=CURRENT_TIME):
			with patch("ghpy.Request.time.sleep") as sleep:
				actual = request.execute()

		def Then_the_reset_time_is_used_for_the_retry():
			sleep.assert_called_once_with(RATE_LIMIT_RESET - CURRENT_TIME)
			assert request.spent == RATE_LIMIT_RESET - CURRENT_TIME
			assert actual is successResponse


def Given_a_rate_limit_reset_that_has_passed():

	RETRY_STATUS = 403
	SUCCESS_STATUS = 200
	RATE_LIMIT_REMAINING = "0"
	RATE_LIMIT_RESET = 99
	CURRENT_TIME = 100
	DEFAULT_DELAY = 3
	URL = "https://example.com/test"
	MAX_RETRIES = 1

	requests = Mock()
	connections = Mock()
	retryResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_the_rate_limit_has_already_reset():

		retryResponse.status = RETRY_STATUS
		retryResponse.headers = {
			"X-RateLimit-Remaining": RATE_LIMIT_REMAINING,
			"X-RateLimit-Reset": str(RATE_LIMIT_RESET),
		}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [retryResponse, successResponse]
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES, delay=DEFAULT_DELAY
		)

		with patch("ghpy.Request.time.time", return_value=CURRENT_TIME):
			with patch("ghpy.Request.time.sleep") as sleep:
				actual = request.execute()

		def Then_the_default_delay_is_used():
			sleep.assert_called_once_with(DEFAULT_DELAY)
			assert request.spent == DEFAULT_DELAY
			assert actual is successResponse


def Given_a_request_with_custom_retry_statuses():

	CUSTOM_RETRY_STATUS = 418
	DEFAULT_RETRY_STATUS = 503
	SUCCESS_STATUS = 200
	URL = "https://example.com/test"
	MAX_RETRIES = 1
	DELAY = 0

	requests = Mock()
	connections = Mock()
	customResponse = Mock(spec=PooledResponse)
	defaultResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_custom_and_default_statuses_are_returned():

		customResponse.status = CUSTOM_RETRY_STATUS
		customResponse.headers = {}

		defaultResponse.status = DEFAULT_RETRY_STATUS
		defaultResponse.headers = {}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [
			customResponse, defaultResponse, successResponse
		]
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=MAX_RETRIES + 1,
			delay=DELAY,
			retryStatuses={CUSTOM_RETRY_STATUS},
		)

		actual = request.execute()

		def Then_both_statuses_are_retried():
			assert connections.request.call_count == 3
			customResponse.close.assert_called_once()
			defaultResponse.close.assert_called_once()
			assert actual is successResponse


def Given_a_post_redirected_with_302():

	REDIRECT_STATUS = 302
	SUCCESS_STATUS = 200
	URL = "https://example.com/upload"
	REDIRECT_URL = "https://example.com/result"
	BODY = b"payload"

	requests = Mock()
	connections = Mock()
	redirectResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_the_post_is_redirected():

		redirectResponse.status = REDIRECT_STATUS
		redirectResponse.headers = {"Location": REDIRECT_URL}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [redirectResponse, successResponse]
		requests.getConnections.side_effect = [connections, connections]

		request = Request(
			requests,
			"POST",
			URL,
			{
				"Content-Length": str(len(BODY)),
				"Content-Type": "application/octet-stream",
			},
			BODY,
			maxRetries=0,
		)

		actual = request.execute()

		def Then_the_redirect_becomes_a_get():
			assert connections.request.call_count == 2
			connections.request.assert_any_call(
				"GET",
				REDIRECT_URL,
				{},
				None,
			)
			assert actual is successResponse
			redirectResponse.close.assert_called_once()


def Given_a_post_redirected_with_307():

	REDIRECT_STATUS = 307
	SUCCESS_STATUS = 200
	URL = "https://example.com/upload"
	REDIRECT_URL = "https://example.com/upload-again"
	BODY = b"payload"
	HEADERS = {
		"Content-Length": str(len(BODY)),
		"Content-Type": "application/octet-stream",
	}

	requests = Mock()
	connections = Mock()
	redirectResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_the_post_is_redirected():

		redirectResponse.status = REDIRECT_STATUS
		redirectResponse.headers = {"Location": REDIRECT_URL}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		connections.request.side_effect = [redirectResponse, successResponse]
		requests.getConnections.return_value = connections

		request = Request(
			requests,
			"POST",
			URL,
			HEADERS.copy(),
			BODY,
			maxRetries=0,
		)

		actual = request.execute()

		def Then_the_post_is_preserved():
			assert connections.request.call_count == 2
			connections.request.assert_any_call(
				"POST",
				REDIRECT_URL,
				HEADERS,
				BODY,
			)
			assert actual is successResponse
			redirectResponse.close.assert_called_once()


def Given_a_cross_origin_redirect():

	REDIRECT_STATUS = 307
	SUCCESS_STATUS = 200
	URL = "https://example.com/upload"
	REDIRECT_URL = "https://other.example.com/upload"
	BODY = b"payload"
	AUTHORIZATION = "Bearer secret"
	PROXY_AUTHORIZATION = "Basic secret"
	CONTENT_TYPE = "application/octet-stream"
	HEADERS = {
		"Authorization": AUTHORIZATION,
		"Proxy-Authorization": PROXY_AUTHORIZATION,
		"Content-Type": CONTENT_TYPE,
	}

	requests = Mock()
	firstConnections = Mock()
	secondConnections = Mock()
	redirectResponse = Mock(spec=PooledResponse)
	successResponse = Mock(spec=PooledResponse)

	def When_the_request_is_redirected_to_another_origin():

		redirectResponse.status = REDIRECT_STATUS
		redirectResponse.headers = {"Location": REDIRECT_URL}

		successResponse.status = SUCCESS_STATUS
		successResponse.headers = {}

		firstConnections.request.return_value = redirectResponse
		secondConnections.request.return_value = successResponse
		requests.getConnections.side_effect = [
			firstConnections, secondConnections
		]

		request = Request(
			requests,
			"POST",
			URL,
			HEADERS.copy(),
			BODY,
			maxRetries=0,
		)

		actual = request.execute()

		def Then_sensitive_headers_are_stripped():
			assert secondConnections.request.call_count == 1
			secondConnections.request.assert_called_once_with(
				"POST",
				REDIRECT_URL,
				{"Content-Type": CONTENT_TYPE},
				BODY,
			)
			assert actual is successResponse
			redirectResponse.close.assert_called_once()


def Given_a_redirect_without_a_location():

	REDIRECT_STATUS = 302
	URL = "https://example.com/test"
	REASON = "Found"

	requests = Mock()
	connections = Mock()
	response = Mock(spec=PooledResponse)

	def When_the_redirect_is_missing_a_location():

		response.status = REDIRECT_STATUS
		response.reason = REASON
		response.headers = {}

		connections.request.return_value = response
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=0,
		)

		with pytest.raises(InvalidRedirectError) as error:
			request.execute()

		actual = error.value

		def Then_the_invalid_redirect_error_is_raised():
			assert actual.url == URL
			assert actual.status == REDIRECT_STATUS
			assert actual.reason == REASON
			assert str(actual) == "Location header not found"
			response.close.assert_called_once()


def Given_too_many_redirects():

	REDIRECT_STATUS = 302
	URL = "https://example.com/test"
	REDIRECT_URL = "https://example.com/redirect"
	REASON = "Found"
	MAX_REDIRECTS = 5

	requests = Mock()
	connections = Mock()
	response = Mock(spec=PooledResponse)

	def When_the_redirect_limit_is_exceeded():

		response.status = REDIRECT_STATUS
		response.reason = REASON
		response.headers = {"Location": REDIRECT_URL}

		connections.request.return_value = response
		requests.getConnections.return_value = connections

		request = Request(
			requests, "GET", URL, {}, None,
			maxRetries=0,
		)

		with pytest.raises(TooManyRedirectsError) as error:
			request.execute()

		actual = error.value

		def Then_the_too_many_redirects_error_is_raised():
			assert actual.url == REDIRECT_URL
			assert actual.status == REDIRECT_STATUS
			assert actual.reason == REASON
			assert str(actual) == "Too many redirects"
			assert connections.request.call_count == MAX_REDIRECTS + 1
			assert response.close.call_count == MAX_REDIRECTS + 1
