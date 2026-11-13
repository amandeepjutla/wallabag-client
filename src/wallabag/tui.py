#!/usr/bin/env python3
# Kera (GPT-6-Astra)
# Created: 2026-09-11
# Revised by Claude Opus 5.5 (claude-opus-5-5): 2026-10-06 (light and dark appearance)
# Revised by Kera (GPT-6.1 Sol): 2026-11-11 (57-column slim layout)
# Revised by Kera (GPT-6 Astra): 2026-11-13 (paging, refresh, and request lifetime)

import os
import sys
from pathlib import Path
from typing import List, Optional

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer
from textual.screen import Screen
from textual.theme import Theme
from textual.widgets import DataTable, Footer, Header, Static, Label

from wallabag.config import Configs
from wallabag.entry import Entry
from wallabag.api.get_list_entries import GetListEntries, Params as ListEntriesParams
from wallabag.api.get_entry import GetEntry
from wallabag.api.update_entry import UpdateEntry, Params as UpdateEntryParams
from wallabag.export.export_factory import ExportFactory
from wallabag.format_type import ScreenType
from wallabag.commands.show import ShowCommandParams
from wallabag.reader_paging import EntryPage, PAGE_SIZE, parse_page
from wallabag.reader_requests import ReaderRequests

# Light and dark. The `appearance` command (~/Dropbox/scripts/_macos) writes
# one word, "light" or "dark", to this file; a missing file means dark. The
# reader looks at start and about once a second after that. vault_reader.py
# and rss_reader.py read the same file and use the same light theme.
MODE_FILE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "appearance" / "mode"


def appearance_mode() -> str:
    try:
        return "light" if MODE_FILE.read_text().strip() == "light" else "dark"
    except OSError:
        return "dark"


# Dark keeps Textual's stock theme. This is its light counterpart, in the
# colours of Tomorrow Day 1991.
DAY_THEME = Theme(
    name="tomorrow-day-1991", dark=False, foreground="#27292c", background="#ffffff",
    surface="#ffffff", panel="#e9ecf0", primary="#3a6399", secondary="#186d73", accent="#a34f12",
    warning="#796000", error="#b02324", success="#356d3b")
APP_THEMES = {"dark": "textual-dark", "light": DAY_THEME.name}


def load_article_page(config: Configs, page: int) -> EntryPage:
    response = GetListEntries(config, {
        ListEntriesParams.COUNT: PAGE_SIZE,
        ListEntriesParams.PAGE: page,
        ListEntriesParams.FILTER_READ: None,
        ListEntriesParams.FILTER_STARRED: None,
        ListEntriesParams.OLDEST: False,
        ListEntriesParams.TAGS: None,
    }).request()
    # Page numbers stay on the configured API; response links are never followed.
    return parse_page(response.response, page)


class ArticleTable(DataTable):
    """Give the title the space left after metadata and the scrollbar."""

    def on_resize(self) -> None:
        # Mount runs before Textual knows the pane size. Measure after layout,
        # and repeat when the pane or its scrollbar changes size.
        self.call_after_refresh(self.fit_title_column)

    def fit_title_column(self) -> None:
        title = self.columns.get("title")
        if title is None or not self.size.width:
            return
        metadata_width = sum(column.get_render_width(self)
                             for column in self.ordered_columns
                             if column.key != "title")
        width = max(8 if self.app.slim else 20, self.scrollable_content_region.width
                    - metadata_width - 2 * self.cell_padding)
        if title.width != width:
            title.width = width
            # Textual 4 has no column-width setter. Invalidate its cached cell
            # rendering and scroll dimensions after changing column metadata.
            self._clear_caches()
            self._require_update_dimensions = True
            self.refresh(layout=True)


class ArticleListScreen(Screen):
    """Browse articles with pine-style navigation."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_article", "Read Article", priority=True),
        Binding("o", "select_article", "Open Article", show=False),
        Binding("r", "toggle_read", "Toggle Read"),
        Binding("s", "toggle_star", "Toggle Star"),
        Binding("l", "load_more", "Load More"),
        Binding("R", "refresh_list", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: Configs, entries: List[Entry], *,
                 next_page: Optional[int] = None, total: Optional[int] = None):
        super().__init__()
        self.config = config
        self.entries = entries
        self._updating = False
        self._loading = False
        self.next_page = next_page
        self.total = total

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main_container"):
            yield ArticleTable(id="articles_table", cursor_type="row")
            yield Label("", id="status_label", markup=False)
        yield Footer()
        yield Static("Enter Read  l More  R Refresh  r Read  s Star  q Quit", classes="slim-help", markup=False)

    def on_mount(self) -> None:
        self.set_class(self.app.slim, "slim")
        table = self.query_one(DataTable)
        if not self.app.slim:
            table.add_column("ID", key="id", width=6)
        table.add_column("●★" if self.app.slim else "Status", key="status", width=2 if self.app.slim else 6)
        table.add_column("Title", key="title", width=20)
        if not self.app.slim:
            table.add_column("Tags", key="tags", width=10)
        table.add_column("Time", key="time", width=5)
        self._append_rows(self.entries)
        self._show_list_status()
        table.focus()
        table.call_after_refresh(table.fit_title_column)

    def _append_rows(self, entries: List[Entry]) -> None:
        table = self.query_one(DataTable)
        for entry in entries:
            cells = [self._get_status_chars(entry), Text(entry.title, no_wrap=True, overflow="ellipsis")]
            if not self.app.slim:
                cells.insert(0, str(entry.entry_id))
                cells.append(Text(entry.get_tags_string() or ""))
            cells.append(f"{entry.reading_time}m" if entry.reading_time else "")
            table.add_row(
                *cells,
                key=str(entry.entry_id),
            )

    def _list_summary(self) -> str:
        if not self.entries:
            return "No articles found. R Refresh"
        count = f"{len(self.entries):,}"
        if self.total is not None:
            count += f" of {self.total:,}"
        continuation = "L More" if self.next_page is not None else "R Refresh"
        return f"{count} articles loaded · {continuation}"

    def _show_list_status(self) -> None:
        self._show_status(self._list_summary() + "\nN unread  R read  * starred")

    def action_load_more(self) -> None:
        if self.next_page is not None and not self._updating:
            self._load_page(refresh=False)

    def action_refresh_list(self) -> None:
        if not self._updating:
            self._load_page(refresh=True)

    @work(group="paging")
    async def _load_page(self, *, refresh: bool) -> None:
        if self._loading or self._updating:
            return
        page_number = 1 if refresh else self.next_page
        if page_number is None:
            return
        # Keep this reader's network actions serial: the existing OAuth helper
        # can refresh and save credentials while creating any API request.
        self._loading = True
        self._show_status("Refreshing articles…" if refresh else "Loading more articles…")
        try:
            page = await self.app.reader_requests.run(load_article_page, self.config, page_number)
        except Exception as error:
            retry = "R" if refresh else "L"
            self._show_status(f"Could not load articles: {error}\n{self._list_summary()} · {retry} Retry")
            return
        finally:
            self._loading = False
        table = self.query_one(DataTable)
        if refresh:
            selected = self._selected_entry()
            selected_id = str(selected.entry_id) if selected is not None else None
            self.entries[:] = page.entries
            table.clear()
            self._append_rows(self.entries)
            row = next((i for i, entry in enumerate(self.entries) if str(entry.entry_id) == selected_id), 0)
            if self.entries:
                table.move_cursor(row=row, animate=False)
            self.next_page, self.total = page.next_page, page.total
        else:
            known = {str(entry.entry_id) for entry in self.entries}
            fresh = [entry for entry in page.entries if str(entry.entry_id) not in known]
            self.entries.extend(fresh)
            self._append_rows(fresh)
            self.next_page, self.total = page.next_page, page.total
            if not fresh:
                self.next_page = None
                self._show_status(f"No new articles returned. R Refresh\n{len(self.entries):,} articles retained.")
                return
        self._show_list_status()
        table.call_after_refresh(table.fit_title_column)

    def _get_status_chars(self, entry: Entry) -> str:
        return ("R" if entry.read else "N") + ("*" if entry.starred else " ")

    def _selected_entry(self) -> Optional[Entry]:
        row = self.query_one(DataTable).cursor_row
        return self.entries[row] if 0 <= row < len(self.entries) else None

    def action_cursor_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_select_article()

    def action_select_article(self) -> None:
        entry = self._selected_entry()
        if entry and not self._updating and not self._loading:
            self.app.push_screen(ArticleViewScreen(self.config, entry))

    def action_toggle_read(self) -> None:
        self._toggle_status(UpdateEntryParams.READ, "read")

    def action_toggle_star(self) -> None:
        self._toggle_status(UpdateEntryParams.STAR, "starred")

    @work
    async def _toggle_status(self, parameter, attribute: str) -> None:
        entry = self._selected_entry()
        if entry is None or self._updating or self._loading:
            return
        self._updating = True
        new_value = not getattr(entry, attribute)
        self._show_status("Updating article…")
        try:
            api = UpdateEntry(self.config, entry.entry_id, {parameter: new_value})
            await self.app.reader_requests.run(api.request)
            setattr(entry, attribute, new_value)
            self._refresh_article_status(entry)
            if attribute == "read":
                self._show_status("Marked as read" if new_value else "Marked as unread")
            else:
                self._show_status("Starred" if new_value else "Unstarred")
        except Exception as error:
            self._show_status(f"Could not update article: {error}")
        finally:
            self._updating = False

    def _show_status(self, message: str) -> None:
        self.query_one("#status_label", Label).update(message)

    def _refresh_article_status(self, entry: Entry) -> None:
        self.query_one(DataTable).update_cell(
            str(entry.entry_id), "status", self._get_status_chars(entry))

    def on_screen_resume(self) -> None:
        # Opening an article marks it read; reflect that when returning.
        table = self.query_one(DataTable)
        if table.row_count:
            for entry in self.entries:
                self._refresh_article_status(entry)

    def action_quit(self) -> None:
        self.app.exit()


class ArticleViewScreen(Screen):
    """Read an article and return to the same list position."""

    BINDINGS = [
        Binding("q", "back_to_list", "Back to List"),
        Binding("escape", "back_to_list", "Back", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("page_down", "page_down", "Page Down"),
        Binding("page_up", "page_up", "Page Up"),
        Binding("home", "scroll_home", "Top"),
        Binding("end", "scroll_end", "Bottom"),
    ]

    def __init__(self, config: Configs, entry: Entry):
        super().__init__()
        self.config = config
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="article_container"):
            if not self.app.slim:
                yield from self.heading_widgets()
            with ScrollableContainer(id="content_scroll"):
                if self.app.slim:
                    yield from self.heading_widgets()
                yield Static("Loading article content…", id="article_content", markup=False)
        yield Footer()
        yield Static("Esc List  j/k Scroll  PgDn Page  q Back", classes="slim-help", markup=False)

    def heading_widgets(self) -> ComposeResult:
        yield Static(self.entry.title, id="breadcrumb", markup=False)
        yield Static(self.entry.url, id="article_url", markup=False)
        details = f"Reading time: {self.entry.reading_time or '?'}m"
        if self.app.slim:
            details += f" · #{self.entry.entry_id}"
            if tags := self.entry.get_tags_string():
                details += f" · {tags}"
        yield Static(details, id="article_meta", markup=False)

    def on_mount(self) -> None:
        self.set_class(self.app.slim, "slim")
        self.query_one("#content_scroll").focus()
        self._load_article_content()

    @work
    async def _load_article_content(self) -> None:
        try:
            response = await self.app.reader_requests.run(GetEntry(self.config, self.entry.entry_id).request)
            full_entry = Entry(response.response)
            params = ShowCommandParams(self.entry.entry_id, ScreenType.TERM, colors=False,
                                       raw=False, image_links=False)
            content = ExportFactory.create(
                full_entry, params, ScreenType.TERM,
                min(80, max(20, self.size.width - (2 if self.app.slim else 6))),
            ).run(include_title=not self.app.slim).strip()
            self.query_one("#article_content", Static).update(
                Text.from_ansi(content or "No content available for this article."))
        except Exception as error:
            self.query_one("#article_content", Static).update(f"Error loading article: {error}")
            return

        if not self.entry.read:
            try:
                await self.app.reader_requests.run(UpdateEntry(self.config, self.entry.entry_id, {
                    UpdateEntryParams.READ: True,
                }).request)
                self.entry.read = True
                for screen in self.app.screen_stack:
                    if isinstance(screen, ArticleListScreen):
                        screen._refresh_article_status(self.entry)
            except Exception as error:
                self.query_one("#article_meta", Static).update(
                    Text(f"Article loaded; could not mark as read: {error}"))

    def action_back_to_list(self) -> None:
        self.app.pop_screen()

    def action_scroll_down(self) -> None:
        self.query_one("#content_scroll", ScrollableContainer).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#content_scroll", ScrollableContainer).scroll_up()

    def action_page_down(self) -> None:
        self.query_one("#content_scroll", ScrollableContainer).scroll_page_down()

    def action_page_up(self) -> None:
        self.query_one("#content_scroll", ScrollableContainer).scroll_page_up()

    def action_scroll_home(self) -> None:
        self.query_one("#content_scroll", ScrollableContainer).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#content_scroll", ScrollableContainer).scroll_end()


class WallabagTUI(App):
    TITLE = "Wallabag"
    BINDINGS = [Binding("q", "quit", "Quit")]
    CSS = """
    #main_container, #article_container { height: 1fr; }
    #articles_table { height: 1fr; }
    #status_label { height: auto; min-height: 1; padding: 0 1; }
    #article_container { padding: 0 1; }
    #breadcrumb { height: auto; text-style: bold; color: $accent; }
    #article_url, #article_meta { height: auto; color: $text-muted; }
    #article_meta { margin-bottom: 1; }
    #content_scroll { height: 1fr; }
    /* Include two padding cells around the 80-column reading area. */
    #article_content { height: auto; width: 100%; max-width: 82; padding: 0 1; }
    .slim-help { display: none; height: 1; padding: 0 1; background: $surface; }
    Screen.slim Footer { display: none; }
    Screen.slim .slim-help { display: block; }
    Screen.slim #article_content { padding: 0; }
    Screen.slim #content_scroll { overflow-x: hidden; }
    """

    def __init__(self, config_path: Optional[str] = None, *, slim: bool = False):
        super().__init__()
        self.slim = slim
        self.config = Configs(config_path)
        self.entries: List[Entry] = []
        self.reader_requests = ReaderRequests()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading articles…", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(DAY_THEME)
        self.follow_appearance()
        self.set_interval(1, self.follow_appearance)
        if not self.config.is_valid():
            self.exit(return_code=1, message="Wallabag is not configured. Run 'wallabag config'.")
            return
        self._load_articles()

    def follow_appearance(self) -> None:
        theme = APP_THEMES[appearance_mode()]
        if self.theme != theme:
            self.theme = theme

    @work
    async def _load_articles(self) -> None:
        try:
            page = await self.reader_requests.run(load_article_page, self.config, 1)
            self.entries = page.entries
            self.push_screen(ArticleListScreen(self.config, self.entries, next_page=page.next_page, total=page.total))
        except Exception as error:
            self.exit(return_code=1, message=Text(f"Error loading articles: {error}"))


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Wallabag TUI - Terminal User Interface')
    parser.add_argument('--config', help='Use custom configuration file')
    parser.add_argument('--slim', action='store_true', help='Use a compact article list and reader for narrow panes')
    args = parser.parse_args()
    try:
        app = WallabagTUI(args.config, slim=args.slim)
        app.run()
        return app.return_code
    except (ValueError, OSError) as error:
        print(f"Wallabag: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
