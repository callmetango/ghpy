import json
import re
import tomllib


with open("pyproject.toml", "rb") as file:
	project = tomllib.load(file)["project"]

versions = [
	match.group(1)
	for classifier in project["classifiers"]
	if (match := re.fullmatch(
		r"Programming Language :: Python :: (\d+\.\d+)",
		classifier,
	))
]

print(json.dumps(versions))
