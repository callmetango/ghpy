# ghpy

*GitHub releases, with retries.*

ghpy is a command-line tool for managing GitHub release assets. It provides a CLI with commands and options similar to [`gh release`](https://cli.github.com/manual/gh_release), focused on uploading, downloading, and waiting for assets. Its goal is to handle these tasks reliably when the networks or things behind them go south.

## Requirements

- Python 3.11 or newer
- A [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) in `GH_TOKEN`

Set the token with:

```sh
export GH_TOKEN=...
```

## Installation

```sh
python -m pip install .
```

## Usage

### Upload assets

Upload one or more files to a release:

```sh
ghpy release upload --repo OWNER/REPO TAG FILE...
```

For example:

```sh
ghpy release upload --repo sonicde-arch/beta x86_64-staging \
	*.pkg.tar.zst
```

Use `--clobber` to replace existing assets:

```sh
ghpy release upload --repo OWNER/REPO --clobber TAG FILE...
```

### Download assets

Download release assets:

```sh
ghpy release download --repo OWNER/REPO TAG
```

Restrict the download to matching asset names with `-p` or `--pattern`:

```sh
ghpy release download --repo OWNER/REPO -p '*.pkg.tar.zst' TAG
```

The option can be specified more than once.

### Wait for assets

Wait until release assets become available:

```sh
ghpy release await-assets --repo OWNER/REPO TAG ASSET...
```

For example:

```sh
ghpy release await-assets --repo sonicde-arch/beta x86_64-staging \
	x86_64-staging.pkg.tar.zst
```

## Retries

Transient network and HTTP failures are retried automatically. The retry behavior can be configured with `--retries`, `--delay`, `--increment`, and `--max-delay`. The retry budget covers the delays between attempts, not the time spent waiting for a request to complete. GitHub's `Retry-After` and rate-limit information are honored when available.

```sh
ghpy release upload --repo OWNER/REPO \
	--retries 12 --delay 2 --increment 2 --max-delay 60 \
	TAG FILE...
```

## Why ghpy?

`ghpy` works around some of the shortcomings of `gh release` when GitHub's networking fails. It provides retries, parallel transfers, meaningful error messages, and increased verbosity on demand.

Its CLI is similar to `gh release`, with a subset of its commands, options, and arguments.

## Development

The goal is to keep ghpy simple and clean with [KISS and DRY](https://www.boldare.com/blog/kiss-yagni-dry-principles/). Each class lives in its own module; the configuration is validated at the boundary. It has snakes and coffee.

Install the development dependencies:

```sh
python -m pip install -e ".[test]"
```

ghpy's tests use a [Given/When/Then](https://martinfowler.com/bliki/GivenWhenThen.html) structure with pytest-describe. They are executable specifications, with fixtures used selectively for reusable context.

Run the tests with:

```sh
python -m pytest
```

## License

GNU Affero General Public License v3.0 only (AGPL-3.0-only).

