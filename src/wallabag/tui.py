#!/usr/bin/env python3

import sys
import os
from pathlib import Path
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, Label
from textual.message import Message
from textual.reactive import reactive

from wallabag.config import Configs
from wallabag.entry import Entry
from wallabag.api.get_list_entries import GetListEntries, Params as ListEntriesParams
from wallabag.api.get_entry import GetEntry
from wallabag.api.update_entry import UpdateEntry, Params as UpdateEntryParams
from wallabag.export.export_factory import ExportFactory
from wallabag.format_type import ScreenType
from wallabag.commands.show import ShowCommandParams


class ArticleListScreen(Screen):
    """Article list view similar to pine's main screen."""
    
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "select_article", "Read Article"),
        Binding("o", "select_article", "Open Article"),
        Binding("r", "toggle_read", "Toggle Read"),
        Binding("s", "toggle_star", "Toggle Star"),
        Binding("q", "quit", "Quit"),
    ]
    
    def __init__(self, config: Configs, entries: List[Entry]):
        super().__init__()
        self.config = config
        self.entries = entries
        self.selected_row = 0
        self.status_message = ""
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="articles_table"),
            Label("", id="status_label"),
            id="main_container"
        )
        yield Footer()
    
    def on_mount(self) -> None:
        table = self.query_one("#articles_table", DataTable)
        table.add_columns("ID", "Status", "Title", "Tags", "Time")
        
        for entry in self.entries:
            status_chars = self._get_status_chars(entry)
            tags_str = entry.get_tags_string() or ""
            time_str = f"{entry.reading_time}m" if entry.reading_time else ""
            
            table.add_row(
                str(entry.entry_id),
                status_chars,
                entry.title,
                tags_str,
                time_str
            )
        
        table.focus()
    
    def _get_status_chars(self, entry: Entry) -> str:
        """Get status characters like pine uses."""
        read_char = "R" if entry.read else "N"
        star_char = "*" if entry.starred else " "
        return f"{read_char}{star_char}"
    
    def action_cursor_down(self) -> None:
        table = self.query_one("#articles_table", DataTable)
        table.action_cursor_down()
    
    def action_cursor_up(self) -> None:
        table = self.query_one("#articles_table", DataTable)
        table.action_cursor_up()
    
    def on_data_table_row_selected(self, event) -> None:
        """Handle when user presses enter on a table row."""
        cursor_row = event.data_table.cursor_row
        if cursor_row < len(self.entries):
            entry = self.entries[cursor_row]
            #self._show_status(f"Opening: {entry.title[:30]}...")
            self.app.push_screen(ArticleViewScreen(self.config, entry))
    
    def action_select_article(self) -> None:
        """Handle 'o' key to open article."""
        table = self.query_one("#articles_table", DataTable)
        cursor_row = table.cursor_row
        if cursor_row < len(self.entries):
            entry = self.entries[cursor_row]
            #self._show_status(f"Opening: {entry.title[:30]}...")
            self.app.push_screen(ArticleViewScreen(self.config, entry))
    
    def action_toggle_read(self) -> None:
        """Toggle read status of selected article."""
        table = self.query_one("#articles_table", DataTable)
        if table.cursor_row < len(self.entries):
            entry = self.entries[table.cursor_row]
            new_read_status = not entry.read
            
            try:
                # Update on server
                api = UpdateEntry(self.config, entry.entry_id, {
                    UpdateEntryParams.READ: new_read_status
                })
                api.request()
                
                # Update local entry
                entry.read = new_read_status
                
                # Update table display using the working method
                status_chars = self._get_status_chars(entry)
                rows = list(table.rows.keys())
                columns = list(table.columns.keys())
                
                if table.cursor_row < len(rows):
                    current_row_key = rows[table.cursor_row]
                    status_col_key = columns[1]  # Status column
                    table.update_cell(current_row_key, status_col_key, status_chars)
                
                # Show status message
                status_text = "Marked as read" if new_read_status else "Marked as unread"
                self._show_status(status_text)
                
            except Exception as e:
                import traceback
                error_msg = f"Error updating read status: {str(e)}"
                self._show_status(error_msg)
                # Log full traceback for debugging
                print(f"Read toggle error: {traceback.format_exc()}")
    
    def action_toggle_star(self) -> None:
        """Toggle star status of selected article."""
        table = self.query_one("#articles_table", DataTable)
        if table.cursor_row < len(self.entries):
            entry = self.entries[table.cursor_row]
            new_star_status = not entry.starred
            
            try:
                # Update on server
                api = UpdateEntry(self.config, entry.entry_id, {
                    UpdateEntryParams.STAR: new_star_status
                })
                api.request()
                
                # Update local entry
                entry.starred = new_star_status
                
                # Update table display using the working method
                status_chars = self._get_status_chars(entry)
                rows = list(table.rows.keys())
                columns = list(table.columns.keys())
                
                if table.cursor_row < len(rows):
                    current_row_key = rows[table.cursor_row]
                    status_col_key = columns[1]  # Status column
                    table.update_cell(current_row_key, status_col_key, status_chars)
                
                # Show status message
                status_text = "Starred" if new_star_status else "Unstarred"
                self._show_status(status_text)
                
            except Exception as e:
                import traceback
                error_msg = f"Error updating star status: {str(e)}"
                self._show_status(error_msg)
                # Log full traceback for debugging
                print(f"Star toggle error: {traceback.format_exc()}")
    
    def _show_status(self, message: str) -> None:
        """Show status message to user."""
        status_label = self.query_one("#status_label", Label)
        status_label.update(message)
        # Clear message after 3 seconds
        self.set_timer(3.0, lambda: status_label.update("j/k=navigate, enter/o=open, r=read, s=star, q=quit"))
    
    def _refresh_article_status(self, entry: Entry) -> None:
        """Refresh the status of a specific article in the table."""
        table = self.query_one("#articles_table", DataTable)
        for i, list_entry in enumerate(self.entries):
            if list_entry.entry_id == entry.entry_id:
                # Update the entry in our list
                self.entries[i] = entry
                # Update the table display
                status_chars = self._get_status_chars(entry)
                # Get the actual row key for this entry
                row_key = self.entry_to_row_key[entry.entry_id]
                table.update_cell(row_key, "Status", status_chars)
                break
    
    def action_quit(self) -> None:
        self.app.exit()


class ArticleViewScreen(Screen):
    """Article reading view similar to pine's message view."""
    
    BINDINGS = [
        Binding("q", "back_to_list", "Back to List"),
        Binding("escape", "back_to_list", "Back to List"),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("up", "scroll_up", "Scroll Up", show=False),
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
        yield Container(
            Static(f"Article View → [bold]{self.entry.title}[/bold]", id="breadcrumb"),
            Static(f"URL: {self.entry.url}", id="article_url"),
            Static(f"Reading time: {self.entry.reading_time}m" if self.entry.reading_time else "Reading time: Unknown", id="article_meta"),
            Static("─" * 50, id="separator"),
            ScrollableContainer(
                Static("Loading article content...", id="article_content"),
                id="content_scroll"
            ),
            id="article_container"
        )
        yield Footer()
    
    def on_mount(self) -> None:
        self._load_article_content()
    
    def _load_article_content(self) -> None:
        """Load full article content."""
        try:
            # Get full article content
            api = GetEntry(self.config, self.entry.entry_id)
            response = api.request()
            full_entry = Entry(response.response)
            
            # Format content for display
            params = ShowCommandParams(
                self.entry.entry_id,
                ScreenType.TERM,
                colors=False,
                raw=False,
                image_links=False
            )
            params.width = '100%'
            
            content = ExportFactory.create(
                full_entry,
                params,
                ScreenType.TERM,
                80  # Use reasonable width for terminal
            ).run()
            
            # Clean up content for better display
            content = content.strip()
            if not content:
                content = "No content available for this article."
            
            # Update content display
            content_widget = self.query_one("#article_content", Static)
            content_widget.update(content)
            
            # Update entry as read when viewing
            if not self.entry.read:
                self._mark_as_read()
            
        except Exception as e:
            import traceback
            content_widget = self.query_one("#article_content", Static)
            error_msg = f"Error loading article: {str(e)}"
            content_widget.update(error_msg)
            # Log full traceback for debugging
            print(f"Article loading error: {traceback.format_exc()}")
    
    def _mark_as_read(self) -> None:
        """Mark article as read when viewed."""
        try:
            api = UpdateEntry(self.config, self.entry.entry_id, {
                UpdateEntryParams.READ: True
            })
            api.request()
            self.entry.read = True
        except Exception:
            # Silently fail - not critical if this doesn't work
            pass
    
    def action_back_to_list(self) -> None:
        self.app.pop_screen()
    
    def action_scroll_down(self) -> None:
        scroll_view = self.query_one("#content_scroll", ScrollableContainer)
        scroll_view.scroll_down()
    
    def action_scroll_up(self) -> None:
        scroll_view = self.query_one("#content_scroll", ScrollableContainer)
        scroll_view.scroll_up()
    
    def action_page_down(self) -> None:
        scroll_view = self.query_one("#content_scroll", ScrollableContainer)
        scroll_view.scroll_page_down()
    
    def action_page_up(self) -> None:
        scroll_view = self.query_one("#content_scroll", ScrollableContainer)
        scroll_view.scroll_page_up()
    
    def action_scroll_home(self) -> None:
        scroll_view = self.query_one("#content_scroll", ScrollableContainer)
        scroll_view.scroll_home()
    
    def action_scroll_end(self) -> None:
        scroll_view = self.query_one("#content_scroll", ScrollableContainer)
        scroll_view.scroll_end()


class WallabagTUI(App):
    """Main TUI application."""
    
    # Explicitly disable CSS loading
    CSS = ""
    CSS_PATH = None
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config = Configs(config_path)
        self.entries: List[Entry] = []
        self.selected_article_index = 0
    
    def on_mount(self) -> None:
        """Load articles on startup."""
        if not self.config.is_valid():
            self.exit(1, "Invalid configuration. Please run 'wallabag config' first.")
            return
        
        self._load_articles()
    
    def _load_articles(self) -> None:
        """Load articles from wallabag."""
        try:
            # Get articles (similar to list command)
            api = GetListEntries(self.config, {
                ListEntriesParams.COUNT: 100,  # Load first 100 articles
                ListEntriesParams.FILTER_READ: None,
                ListEntriesParams.FILTER_STARRED: None,
                ListEntriesParams.OLDEST: False,
                ListEntriesParams.TAGS: None
            })
            
            response = api.request()
            self.entries = Entry.create_list(response.response['_embedded']['items'])
            
            # Push article list screen
            self.push_screen(ArticleListScreen(self.config, self.entries))
            
        except Exception as e:
            self.exit(1, f"Error loading articles: {str(e)}")


def main():
    """Entry point for wallabag-tui command."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Wallabag TUI - Terminal User Interface')
    parser.add_argument('--config', help='Use custom configuration file')
    args = parser.parse_args()
    
    app = WallabagTUI(args.config)
    app.run()


if __name__ == "__main__":
    main()
