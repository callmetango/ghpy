import logging
import os

from darg import AppendValue, Cli, OneOrMore, Type, argument, command, dispatch, flag, option
from darg.converters import ExistingFile, NonNegative

from .actions import SplitRepository
from .errors.GhpyError import GhpyError
from .errors.OperationError import OperationError
from .Release import Release
from .Releases import Releases
from .Request import MAX_DELAY, MAX_RETRIES, RETRY_DELAY, RETRY_INCREMENT
from .RequestFactory import RequestFactory


def addRetryOptions():
	option("retries", NonNegative, default=MAX_RETRIES)
	option("delay", NonNegative, default=RETRY_DELAY)
	option("increment", NonNegative, default=RETRY_INCREMENT)
	option("max-delay", NonNegative, default=MAX_DELAY, dest="maxDelay")


def createCli() -> Cli:
	cli = Cli(
		name="ghpy",
		about="GitHub release asset tool",
	)

	with cli:
		with command("release", about="Manage releases"):
			with command("upload", func=Release.uploadAssets,
					about="Upload release assets"):
				option("repo", action=SplitRepository, required=True)
				flag("verbose", alias="v")
				addRetryOptions()
				flag("clobber")
				argument("tag")
				argument("files", OneOrMore, ExistingFile)

			with command("download", func=Release.downloadAssets,
					about="Download release assets"):
				option("repo", action=SplitRepository, required=True)
				flag("verbose", alias="v")
				addRetryOptions()
				option("pattern", AppendValue, alias="p", dest="patterns")
				argument("tag")

			with command( "await-assets", func=Release.awaitAssets,
					about="Wait for release assets"):
				option("repo", action=SplitRepository, required=True)
				flag("verbose", alias="v")
				addRetryOptions()
				argument("tag")
				argument("names", OneOrMore)

	return cli


def main() -> int:
	args = createCli().parse_args()

	logging.basicConfig(level=logging.INFO if args.verbose else logging.ERROR,
			format="%(message)s")

	token = os.environ["GH_TOKEN"]

	try:
		requests = RequestFactory(maxRetries=args.retries, delay=args.delay,
				increment=args.increment, maxDelay=args.maxDelay)
		releases = Releases(token, requests)
		release = releases.getRelease(args.owner, args.repo, args.tag)
		for name in ("delay", "increment", "maxDelay", "retries", "owner",
			   "repo", "tag", "verbose"):
			hasattr(args, name) and delattr(args, name)
		dispatch(args, release)
	except OperationError:
		return 1
	except GhpyError as error:
		logging.error("%s", error)
		return 1

	return 0
