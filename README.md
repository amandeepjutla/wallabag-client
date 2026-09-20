# wallabag-client

A terminal reader and command-line client for [wallabag](https://wallabag.org/),
based on [Artur Shaik's client](https://github.com/artur-shaik/wallabag-client).
Forked in July 2025 with a TUI interface added by Claude Sonnet 4.

README based on the upstream documentation authored by Kera (GPT-6 Astra) on 
2026-09-11.

Later revisions by Kera (GPT-6 Astra):

- **2026-09-12:** Revised the README for Pixi.
- **2026-09-20:** Documented the reader's 80-character soft wrapping.

## Use

```sh
wallabag                       # Open the terminal reader
wallabag list                  # List articles through the CLI
wallabag --help                # Show CLI commands
wallabag --cli --version        # Show the installed client version
wallabag config                # Configure a Wallabag account
wallabag --tui --config /path/to/config.ini
```

With no arguments, the launcher opens the reader. Arguments select the original
CLI; `--tui` passes options to the reader and `--cli` explicitly selects the CLI.
The CLI supports adding, listing, reading, starring, tagging, exporting, and
deleting entries, plus annotations and opening entries in a browser.

| Key | Reader action |
| --- | --- |
| J / K, arrows | Move through the article list |
| Enter / O | Read the selected article |
| R | Toggle read status |
| S | Toggle starred status |
| Page Up / Page Down | Scroll article text |
| Home / End | Jump to the beginning or end |
| Q / Escape | Return from an article |
| Q | Quit from the article list |

Article text soft-wraps at 80 characters, reflowing to fit narrower terminals.
Wrapping changes the display only; article text and paragraph breaks are preserved.

Opening an article marks it read after its content loads successfully. Read and
star actions synchronize with the server. The reader requires an internet
connection and a reachable Wallabag API.

## Install or restore with Pixi

The complete project lives in `~/Dropbox/tools/wallabag-client` and is versioned
at <https://github.com/amandeepjutla/wallabag-client>. Install
[Pixi](https://pixi.prefix.dev/latest/installation/), then:

```sh
mkdir -p "$HOME/Dropbox/tools"
git clone https://github.com/amandeepjutla/wallabag-client.git \
    "$HOME/Dropbox/tools/wallabag-client"
cd "$HOME/Dropbox/tools/wallabag-client"
pixi install --locked
mkdir -p "$HOME/Dropbox/scripts/_platform_independent"
install -m 755 wallabag "$HOME/Dropbox/scripts/_platform_independent/wallabag"
wallabag --help
```

`~/Dropbox/scripts/_platform_independent` must be on PATH. Its launcher is a
standalone file; a matching copy is tracked in this repository for restoration.
Running `./wallabag` in a checkout uses that checkout. `WALLABAG_PROJECT` overrides
the project location for an installed launcher.

`pixi.toml` and `pixi.lock` define Python 3.13, the runtime dependencies, and the
local package installation. Textual is constrained to 4.0 for the reader's table
layout. Dependencies come from conda-forge except Delorean 1.0.0, which is pinned
from PyPI. The lock targets Apple Silicon macOS and Linux x86-64; runtime checks
are performed on macOS.

The committed `.pixi/config.toml` enables Pixi's
[detached environments](https://pixi.prefix.dev/latest/reference/pixi_configuration/#detached-environments).
Python and installed packages live in the machine cache outside Dropbox and are
recreated with `pixi install --locked`. All application source, build definitions,
launcher code, and tests live in this repository. The launcher automatically
selects the locked environment.

## Account configuration

Both interfaces use `~/.config/wallabag-cli/config.ini`, or the corresponding
location under `XDG_CONFIG_HOME`. An existing configuration is reused. For a new
account, run `wallabag config` and provide the server URL, username, password,
OAuth client ID, and client secret from the Wallabag server's API client settings.
A custom file can be selected with `wallabag --config /path/to/config.ini list`
or `wallabag --tui --config /path/to/config.ini`.

Credentials remain outside the repository. Keep the config private: the existing
credential encryption is local obfuscation. Its `api.encryption_hostname` field
preserves the original hostname used for encryption. If a legacy configuration
fails to decrypt after a hostname change, restore that field to the exact original
hostname or run `wallabag config`. Moving to a different operating-system username
also requires reconfiguration. The application refreshes its cached access token
as needed, so the config must be writable by its owner.

## Development and verification

```sh
pixi install --locked --all
pixi run start                 # Reader
pixi run cli --help            # CLI
pixi run test-reader           # Offline reader and API regressions
pixi run -e dev test           # Complete offline test suite
```

The package is installed from this checkout in editable mode. Source edits take
effect immediately. After changing dependencies, run `pixi install --all`, test,
and commit both the manifest and lockfile. After updating the launcher, install
its new copy into `~/Dropbox/scripts/_platform_independent/wallabag`.

Tests cover the original CLI/API behavior and the local repairs: saved credential
recovery, OAuth request handling, article loading and scrolling, terminal resizing,
read/star updates, error handling, and clean exit. Server interactions in these
tests are mocked.

The inherited `flake.nix` remains available as historical Nix setup; Pixi is the
maintained installation and test workflow for this fork.
