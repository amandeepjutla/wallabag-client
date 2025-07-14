# wallabag-client

Wallabag-client is a command line client for the self hosted read-it-later app [wallabag](https://www.wallabag.org/). Unlike to other services, wallabag is free and open source.

Wallabag-client is refactored version of existed wallabag-cli tool.

You can read additional info [here](https://shaik.link/wallabag-client-features.html)

## Terminal user interface

This fork adds a rudimentary TUI. Navigate with `j` and  `k,' press `o` to open an article, and toggle read/star status with `r` and `s`. Both the original CLI (`wallabag`) and new TUI (`wallabag-tui`) are available

### Quick Start

```bash
# Clone and install
git clone https://github.com/amandeepjutla/wallabag-client.git
cd wallabag-client
pip install -e .

# Configure wallabag (required for both CLI and TUI)
wallabag config

# Use the original CLI
wallabag list

# Use the new TUI
wallabag-tui
```

### TUI Key Bindings

- `j/k` or `↑/↓` - Navigate article list
- `Enter` or `o` - Read selected article
- `r` - Toggle read status
- `s` - Toggle star status
- `q` - Quit/Back
- `Page Up/Down` - Scroll article content
- `Home/End` - Jump to top/bottom of article

--------------------------------------------------------------------------------

## Features

### Command Line Interface (CLI)
- List entries (filterable tabulated output with nerd icons);
- Show the content of an entry with custom width and alignment;
- Add new entries;
- Delete entries;
- Mark existing entries as read;
- Mark existing entries as starred;
- Change the title of existing entries;
- Tags support;
- Annotations support;
- Opening entries in browser;
- Showing entry information;
- Export entry to file.

### Terminal User Interface (TUI) - New!
- Interactive article browsing with pine-style navigation;
- Real-time article reading with smooth scrolling;
- Instant read/star status toggles with server sync;
- Professional interface with status indicators;
- Keyboard-driven workflow for efficient article management.

## Installation

### From PyPI (Original version without TUI)
`sudo pip3 install wallabag-client`

### From Source (With TUI support)
```bash
git clone https://github.com/your-username/wallabag-client.git
cd wallabag-client
pip install -e .
```

**Note**: The TUI requires the `textual` dependency which is included in the development installation but not in the PyPI version.

## Usage

### Command Line Interface (CLI)

`wallabag --help`

```
Usage: wallabag [OPTIONS] COMMAND [ARGS]...

Options:
  --config TEXT       Use custom configuration file
  --debug             Enable debug logging to stdout
  --debug-level TEXT  Debug level
  --version           Show the version and exit.
  -h, --help          Show this message and exit.

Commands:
  add             Add a new entry to wallabag.
  anno            Annotation commands.
  config          Start configuration.
  delete          Delete an entry from wallabag.
  delete-by-tags  Delete entries from wallabag by tags.
  export          Export entry to file.
  info            Get entry information.
  list            List the entries on the wallabag account.
  open            Open entry in browser.
  read            Toggle the read-status of an existing entry.
  repl            Start an interactive shell.
  show            Show the text of an entry.
  star            Toggle the starred-status of an existing entry.
  tags            Retrieve and print all tags.
  update          Toggle the read or starred status or change the title of...
  update-by-tags  Set the read or starred status of an existing entries...
```

### Terminal User Interface (TUI)

First, make sure you have configured wallabag:
```bash
wallabag config
```

Then start the TUI:
```bash
wallabag-tui
```

The TUI provides an interactive interface for browsing and reading your wallabag articles. Use the keyboard shortcuts listed above to navigate and manage your articles efficiently.

## Install shell completion (zsh)

A completion script for zsh is provided in the directory `completion/zsh/_wallabag`.

Installation can vary based on your zsh settings and environment. Most importantly, the file has to be placed in one of the directories contained in the `$fpath` variable and then autoloaded.

If you want to install the completion script for all users, you can do the following:

```sh
mkdir -p /usr/local/share/zsh/site-functions
cp _wallabag /usr/local/share/zsh/site-functions
```

and restart zsh.

A better option is to have a directory in your home for local completion scripts, but setting this up is beyond the scope of these instructions. You may refer to [this answer on Stackoverflow](https://stackoverflow.com/a/67161186) for more details.
