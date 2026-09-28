from argparse import Action


class SplitRepository(Action):
	def __call__(self, parser, namespace, value, option_string=None):
		parts = value.split("/")

		if len(parts) != 2 or not all(parts):
			parser.error("argument --repo: must be in OWNER/REPO format")

		namespace.owner = parts[0]
		namespace.repo = parts[1]
