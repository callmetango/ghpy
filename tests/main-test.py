from pathlib import Path
from unittest.mock import ANY, Mock, patch

from ghpy.errors.GhpyError import GhpyError
from ghpy.errors.OperationError import OperationError
from ghpy.main import main


def Given_a_successful_command():

	OWNER = "owner"
	REPO = "repo"
	TAG = "v1"
	FILE = __file__
	FILE_PATH = Path(FILE)

	ARGS = [
		"ghpy", "release", "upload",
		"--repo", f"{OWNER}/{REPO}",
		TAG, FILE,
	]

	release = Mock()
	releases = Mock()
	releases.getRelease.return_value = release

	def When_the_command_is_run():

		with patch("sys.argv", ARGS):
			with patch("ghpy.main.Releases", return_value=releases):
				with patch("ghpy.main.dispatch") as dispatch:
					result = main()

		def Then_the_command_is_dispatched():

			releases.getRelease.assert_called_once_with(OWNER, REPO, TAG)
			dispatch.assert_called_once_with(ANY, release)

			namespace = dispatch.call_args.args[0]
			assert namespace.files == [FILE_PATH]

		def Then_the_command_succeeds():
			assert result == 0


def Given_a_command_that_fails_with_an_operation_error():

	ARGS = [
		"ghpy", "release", "upload",
		"--repo", "owner/repo",
		"v1", __file__,
	]

	release = Mock()
	releases = Mock()
	releases.getRelease.return_value = release

	def When_the_command_is_run():

		with patch("sys.argv", ARGS):
			with patch("ghpy.main.Releases", return_value=releases):
				with patch("ghpy.main.dispatch",
						side_effect=OperationError("Operation failed")):
					result = main()

		def Then_the_command_fails():
			assert result == 1


def Given_a_command_that_fails_with_a_ghpy_error():

	ERROR = GhpyError("Operation failed")

	ARGS = [
		"ghpy", "release", "upload",
		"--repo", "owner/repo",
		"v1", __file__,
	]

	releases = Mock()
	releases.getRelease.side_effect = ERROR

	def When_the_command_is_run():

		with patch("sys.argv", ARGS):
			with patch("ghpy.main.Releases", return_value=releases):
				with patch("ghpy.main.logging.error") as error:
					result = main()

		def Then_the_command_fails():
			assert result == 1

		def Then_the_error_is_reported():
			error.assert_called_once_with("%s", ERROR)
