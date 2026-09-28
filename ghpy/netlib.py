from urllib.parse import urlsplit

def origin(url: str) -> tuple[str, str, int]:
	parts = urlsplit(url)

	scheme = parts.scheme.lower()
	if scheme not in {"http", "https"}:
		raise ValueError(f"Unsupported URL scheme: {scheme!r}")

	host = (parts.hostname or "").lower()
	if not host:
		raise ValueError("URL has no host")

	if parts.port is not None:
		port = parts.port
	elif scheme == "https":
		port = 443
	else:
		port = 80

	return scheme, host, port


def sameOrigin(url1: str, url2: str) -> bool:
	return origin(url1) == origin(url2)


def stripHeaders(headers: dict[str, str], excluded: set[str]) -> dict[str, str]:
	return {
		key: value for key, value in headers.items()
		if key.lower() not in excluded
	}
