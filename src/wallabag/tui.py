#!/usr/bin/env python3
# Kera (GPT-6-Astra)
# Created: 2026-09-11

import asyncio
import sys
from typing import List, Optional

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, Label

from wallabag.config import Configs
from wallabag.entry import Entry
from wallabag.api.get_list_entries import GetListEntries, Params as ListEntriesParams
from wallabag.api.get_entry import GetEntry
from wallabag.api.update_entry import UpdateEntry, Params as UpdateEntryParams
from wallabag.export.export_factory import ExportFactory
from wallabag.format_type import ScreenType
from wallabag.commands.show import ShowCommandParams


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
        width = max(20, self.scrollable_content_region.width
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
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: Configs, entries: List[Entry]):
        super().__init__()
        self.config = config
        self.entries = entries
        self._updating = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main_container"):
            yield ArticleTable(id="articles_table", cursor_type="row")
            yield Label("", id="status_label", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("ID", key="id", width=6)
        table.add_column("Status", key="status", width=6)
        table.add_column("Title", key="title", width=20)
        table.add_column("Tags", key="tags", width=10)
        table.add_column("Time", key="time", width=5)
        for entry in self.entries:
            table.add_row(
                str(entry.entry_id), self._get_status_chars(entry),
                Text(entry.title, no_wrap=True, overflow="ellipsis"),
                Text(entry.get_tags_string() or ""),
                f"{entry.reading_time}m" if entry.reading_time else "",
                key=str(entry.entry_id),
            )
        self._show_status(f"{len(self.entries)} articles. N = unread; R = read; * = starred."
                          if self.entries else "No articles found.")
        table.focus()
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
        if entry and not self._updating:
            self.app.push_screen(ArticleViewScreen(self.config, entry))

    def action_toggle_read(self) -> None:
        self._toggle_status(UpdateEntryParams.READ, "read")

    def action_toggle_star(self) -> None:
        self._toggle_status(UpdateEntryParams.STAR, "starred")

    @work
    async def _toggle_status(self, parameter, attribute: str) -> None:
        entry = self._selected_entry()
        if entry is None or self._updating:
            return
        self._updating = True
        new_value = not getattr(entry, attribute)
        self._show_status("Updating article…")
        try:
            api = UpdateEntry(self.config, entry.entry_id, {parameter: new_value})
            await asyncio.to_thread(api.request)
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
            yield Static(self.entry.title, id="breadcrumb", markup=False)
            yield Static(self.entry.url, id="article_url", markup=False)
            yield Static(f"Reading time: {self.entry.reading_time or '?'}m", id="article_meta")
            with ScrollableContainer(id="content_scroll"):
                yield Static("Loading article content…", id="article_content", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#content_scroll").focus()
        self._load_article_content()

    @work
    async def _load_article_content(self) -> None:
        try:
            response = await asyncio.to_thread(GetEntry(self.config, self.entry.entry_id).request)
            full_entry = Entry(response.response)
            params = ShowCommandParams(self.entry.entry_id, ScreenType.TERM, colors=False,
                                       raw=False, image_links=False)
            content = ExportFactory.create(
                full_entry, params, ScreenType.TERM,
                max(20, self.size.width - 6),
            ).run().strip()
            self.query_one("#article_content", Static).update(
                Text.from_ansi(content or "No content available for this article."))
        except Exception as error:
            self.query_one("#article_content", Static).update(f"Error loading article: {error}")
            return

        if not self.entry.read:
            try:
                await asyncio.to_thread(UpdateEntry(self.config, self.entry.entry_id, {
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
    #article_content { height: auto; padding: 0 1; }
    """

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config = Configs(config_path)
        self.entries: List[Entry] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading articles…", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        if not self.config.is_valid():
            self.exit(return_code=1, message="Wallabag is not configured. Run 'wallabag config'.")
            return
        self._load_articles()

    @work
    async def _load_articles(self) -> None:
        try:
            api = GetListEntries(self.config, {
                ListEntriesParams.COUNT: 100,
                ListEntriesParams.FILTER_READ: None,
                ListEntriesParams.FILTER_STARRED: None,
                ListEntriesParams.OLDEST: False,
                ListEntriesParams.TAGS: None,
            })
            response = await asyncio.to_thread(api.request)
            self.entries = Entry.create_list(response.response['_embedded']['items'])
            self.push_screen(ArticleListScreen(self.config, self.entries))
        except Exception as error:
            self.exit(return_code=1, message=Text(f"Error loading articles: {error}"))


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Wallabag TUI - Terminal User Interface')
    parser.add_argument('--config', help='Use custom configuration file')
    args = parser.parse_args()
    try:
        app = WallabagTUI(args.config)
        app.run()
        return app.return_code
    except (ValueError, OSError) as error:
        print(f"Wallabag: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
