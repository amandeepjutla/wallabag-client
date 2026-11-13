# Kera (GPT-6 Astra). Created 2026-11-13.
"""Offline pagination, concurrency, and read-state acceptance for the reader."""
import asyncio
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from textual.widgets import DataTable, Label

from wallabag import tui
from wallabag.api.api import RequestException, ValueException
from wallabag.api.get_list_entries import GetListEntries, Params
from wallabag.reader_paging import parse_page

if __package__:
    from .test_repair import article, configure
else:
    from test_repair import article, configure


def payload(ids, *, page=1, pages=1, total=None):
    items = [article(i) for i in ids]
    return {"page": page, "pages": pages, "total": len(items) if total is None else total,
            "limit": 100, "_embedded": {"items": items}}


class PageTests(unittest.TestCase):
    def test_explicit_page_is_optional_and_validated(self):
        self.assertNotIn("page", GetListEntries(None, {Params.COUNT: 100})._get_params())
        self.assertEqual(GetListEntries(None, {Params.COUNT: 100, Params.PAGE: 2})._get_params(),
                         {"perPage": 100, "detail": "metadata", "page": 2})
        for invalid in (None, 0, -1, True, "2", 1.5):
            with self.subTest(page=invalid), self.assertRaises(ValueException):
                GetListEntries(None, {Params.COUNT: 100, Params.PAGE: invalid})._get_params()

    def test_metadata_deduplication_and_untrusted_links(self):
        data = payload([1, 1, 2], pages=3, total=202)
        data["_links"] = {"next": {"href": "https://unrelated.invalid/private"}}
        page = parse_page(data, 1)
        self.assertEqual([entry.entry_id for entry in page.entries], [1, 2])
        self.assertEqual((page.next_page, page.total), (2, 202))
        self.assertIsNone(parse_page(payload([9], page=3, pages=3, total=201), 3).next_page)

    def test_missing_metadata_short_pages_and_empty_pages(self):
        self.assertEqual(parse_page({"_embedded": {"items": [article(i) for i in range(100)]}}, 1).next_page, 2)
        self.assertIsNone(parse_page({"_embedded": {"items": [article(1)]}}, 1).next_page)
        self.assertIsNone(parse_page(payload([], page=2, pages=9, total=800), 2).next_page)
        data = {"limit": 2, "total": 4, "_embedded": {"items": [article(1), article(2)]}}
        self.assertEqual(parse_page(data, 1).next_page, 2)
        self.assertIsNone(parse_page(data, 2).next_page)

    def test_invalid_metadata_and_wrong_pages_are_explicit_errors(self):
        for data in (None, [], {}, {"_embedded": []}, {"_embedded": {"items": None}},
                     payload([1], page=2), payload([1], page=True), payload([1], pages="3"),
                     payload([1], total=-1), {**payload([1]), "limit": 0},
                     {"_embedded": {"items": [{"id": []}]}}):
            with self.subTest(payload=data), self.assertRaises(ValueError):
                parse_page(data, 1)


class PagingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.ini"
        configure(self.path)
        self.pages = {1: payload(range(1, 101), pages=3, total=205),
                      2: payload(range(101, 201), page=2, pages=3, total=205),
                      3: payload(range(201, 206), page=3, pages=3, total=205)}
        self.requests, self.updates = [], []
        self.block_page = None
        self.release, self.started = threading.Event(), threading.Event()
        self.addCleanup(self.release.set)
        self.fail_page = None
        self.block_update = False
        for mock in [patch.object(tui.GetListEntries, "request", autospec=True, side_effect=self.list_entries),
                     patch.object(tui.UpdateEntry, "request", autospec=True, side_effect=self.update),
                     patch.object(tui.GetEntry, "request", autospec=True,
                                  side_effect=lambda api: SimpleNamespace(response=article(api.entry_id)))]:
            mock.start()
            self.addCleanup(mock.stop)

    def list_entries(self, api):
        page = api._get_params()["page"]
        self.requests.append(page)
        if page == self.block_page:
            self.started.set()
            self.release.wait(5)
        if page == self.fail_page:
            raise RequestException("fixture unavailable")
        return SimpleNamespace(response=self.pages[page])

    def update(self, api):
        if self.block_update:
            self.started.set()
            self.release.wait(5)
        self.updates.append((api.entry_id, api._get_data()))
        return SimpleNamespace(response={})

    async def launch(self, *, slim=False, size=(110, 36)):
        self.app = tui.WallabagTUI(str(self.path), slim=slim)
        context = self.app.run_test(size=size)
        pilot = await context.__aenter__()
        self.addAsyncCleanup(context.__aexit__, None, None, None)
        await self.settle(pilot)
        return self.app.screen, pilot

    async def settle(self, pilot):
        await self.app.workers.wait_for_complete()
        await pilot.pause()

    def screenshot(self, filename):
        if directory := os.environ.get("PAGING_QA_DIR"):
            self.app.save_screenshot(filename, path=directory)

    async def test_load_all_pages_keep_selection_and_toggle_correct_new_row(self):
        screen, pilot = await self.launch()
        table = screen.query_one(DataTable)
        table.move_cursor(row=45, animate=False)
        await pilot.pause()
        scroll = table.scroll_y
        self.assertIn("100 of 205", str(screen.query_one(Label).renderable))
        await pilot.press("l")
        await self.settle(pilot)
        self.assertEqual((len(screen.entries), table.row_count, table.cursor_row, table.scroll_y), (200, 200, 45, scroll))
        self.assertEqual(self.requests, [1, 2])
        self.assertEqual(self.updates, [])
        self.screenshot("paging-full.svg")
        await pilot.press("l", "l")
        await self.settle(pilot)
        self.assertEqual(self.requests, [1, 2, 3])
        self.assertEqual(len(screen.entries), 205)
        self.assertIsNone(screen.next_page)
        table.move_cursor(row=200, animate=False)
        await pilot.press("s")
        await self.settle(pilot)
        self.assertEqual(self.updates, [(201, {"starred": 1})])
        self.assertEqual(table.get_cell("201", "status"), "N*")

    async def test_page_failure_retries_without_losing_loaded_items(self):
        screen, pilot = await self.launch(slim=True, size=(57, 39))
        self.fail_page = 2
        await pilot.press("l")
        await self.settle(pilot)
        self.assertEqual((len(screen.entries), screen.next_page), (100, 2))
        self.assertIn("L Retry", str(screen.query_one(Label).renderable))
        self.screenshot("paging-error.svg")
        self.fail_page = None
        await pilot.press("l")
        await self.settle(pilot)
        self.assertEqual((len(screen.entries), screen.next_page), (200, 3))
        self.assertEqual(self.requests, [1, 2, 2])
        self.assertEqual(self.updates, [])

    async def test_duplicates_preserve_local_read_state_and_stop_repeated_page(self):
        screen, pilot = await self.launch()
        screen.entries[-1].read = True
        self.pages[2] = payload([100, 100, 101], page=2, pages=3, total=205)
        await pilot.press("l")
        await self.settle(pilot)
        self.assertEqual(len(screen.entries), 101)
        self.assertTrue(screen.entries[99].read)
        self.pages[3] = payload([100, 101], page=3, pages=4, total=205)
        await pilot.press("l")
        await self.settle(pilot)
        self.assertEqual(len(screen.entries), 101)
        self.assertIsNone(screen.next_page)
        self.assertIn("No new articles", str(screen.query_one(Label).renderable))
        await pilot.press("l")
        self.assertEqual(self.requests, [1, 2, 3])
        self.assertEqual(self.updates, [])

    async def test_refresh_reorders_by_identity_and_preserves_list_on_error(self):
        screen, pilot = await self.launch()
        table = screen.query_one(DataTable)
        table.move_cursor(row=45, animate=False)
        self.pages[1] = payload([77, 46, 12], pages=1)
        await pilot.press("R")
        await self.settle(pilot)
        self.assertEqual(table.cursor_row, 1)
        self.assertEqual(screen._selected_entry().entry_id, 46)
        self.assertIs(self.app.entries, screen.entries)
        self.assertIsNone(screen.next_page)
        self.fail_page = 1
        await pilot.press("R")
        await self.settle(pilot)
        self.assertEqual([entry.entry_id for entry in screen.entries], [77, 46, 12])
        self.assertEqual(table.cursor_row, 1)
        self.assertIn("R Retry", str(screen.query_one(Label).renderable))
        self.fail_page = None
        self.pages[1] = payload([77, 12], pages=1)
        await pilot.press("R")
        await self.settle(pilot)
        self.assertEqual(table.cursor_row, 0)
        self.assertEqual(self.updates, [])

    async def test_repeated_keys_and_refresh_during_load_make_one_request(self):
        screen, pilot = await self.launch()
        self.block_page = 2
        await pilot.press("l")
        self.assertTrue(await asyncio.to_thread(self.started.wait, 1))
        await pilot.press("l", "l", "R")
        self.assertEqual(self.requests, [1, 2])
        self.release.set()
        await self.settle(pilot)
        self.assertEqual(len(screen.entries), 200)
        self.assertEqual(self.updates, [])

    async def test_page_loading_serializes_article_requests_and_keeps_row(self):
        screen, pilot = await self.launch(slim=True, size=(57, 39))
        table = screen.query_one(DataTable)
        table.move_cursor(row=2, animate=False)
        self.block_page = 2
        await pilot.press("l")
        self.assertTrue(await asyncio.to_thread(self.started.wait, 1))
        await pilot.press("enter", "r", "s")
        await pilot.pause()
        self.assertIs(self.app.screen, screen)
        self.assertEqual(self.updates, [])
        self.release.set()
        await self.settle(pilot)
        await pilot.press("enter")
        await self.settle(pilot)
        self.assertIsInstance(self.app.screen, tui.ArticleViewScreen)
        await pilot.press("escape")
        await pilot.pause()
        self.assertEqual((table.row_count, table.cursor_row), (200, 2))
        self.assertEqual(self.updates, [(3, {"archive": 1})])

    async def test_refresh_blocks_state_changes_until_result_is_installed(self):
        screen, pilot = await self.launch()
        self.block_page = 1
        await pilot.press("R")
        self.assertTrue(await asyncio.to_thread(self.started.wait, 1))
        await pilot.press("r", "s", "enter")
        self.assertIs(self.app.screen, screen)
        self.assertEqual(self.updates, [])
        self.release.set()
        await self.settle(pilot)
        self.assertFalse(screen._loading)

    async def test_quit_during_request_cancels_ui_completion(self):
        screen, pilot = await self.launch()
        self.block_page = 2
        await pilot.press("l")
        self.assertTrue(await asyncio.to_thread(self.started.wait, 1))
        await asyncio.wait_for(pilot.press("q"), 1)
        self.release.set()
        self.assertFalse(self.app.is_running)
        self.assertEqual(self.updates, [])

    async def test_status_update_serializes_later_page_and_refresh_requests(self):
        screen, pilot = await self.launch()
        self.block_update = True
        await pilot.press("s")
        self.assertTrue(await asyncio.to_thread(self.started.wait, 1))
        await pilot.press("l", "R")
        self.assertEqual(self.requests, [1])
        self.release.set()
        await self.settle(pilot)
        self.assertEqual(self.updates, [(1, {"starred": 1})])
        await pilot.press("l")
        await self.settle(pilot)
        self.assertEqual(self.requests, [1, 2])
        self.assertTrue(screen.entries[0].starred)

    async def test_return_during_article_load_keeps_later_paging_serial(self):
        screen, pilot = await self.launch()
        article_started, article_release = threading.Event(), threading.Event()
        self.addCleanup(article_release.set)

        def slow_article(api):
            article_started.set()
            article_release.wait(5)
            return SimpleNamespace(response=article(api.entry_id))

        with patch.object(tui.GetEntry, "request", new=slow_article):
            try:
                await pilot.press("enter")
                self.assertTrue(await asyncio.to_thread(article_started.wait, 1))
                await pilot.press("escape", "l")
                await pilot.pause()
                self.assertIs(self.app.screen, screen)
                self.assertEqual(self.requests, [1], "paging must wait for the cancelled worker's actual HTTP call")
                self.assertEqual(self.updates, [])
            finally:
                article_release.set()
            await self.settle(pilot)
        self.assertEqual(self.requests, [1, 2])
        self.assertEqual(len(screen.entries), 200)
        self.assertEqual(self.updates, [], "leaving before content arrives must not mark the article read")

    async def test_cancelled_second_article_is_not_requested_after_first_finishes(self):
        screen, pilot = await self.launch()
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        reads = []

        def slow_article(api):
            reads.append(api.entry_id)
            if api.entry_id == 1:
                started.set()
                release.wait(5)
            return SimpleNamespace(response=article(api.entry_id))

        with patch.object(tui.GetEntry, "request", new=slow_article):
            try:
                await pilot.press("enter")
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                await pilot.press("escape", "j", "enter")
                await pilot.pause()
                self.assertIsInstance(self.app.screen, tui.ArticleViewScreen)
                await pilot.press("escape")
                await pilot.pause()
                self.assertIs(self.app.screen, screen)
                self.assertEqual(reads, [1])
            finally:
                release.set()
            # A subsequent request waits for all earlier lock holders and makes
            # the cancelled queued operation's completion observable.
            await self.app.reader_requests.run(lambda: None)
            await self.settle(pilot)
        self.assertEqual(reads, [1])
        self.assertEqual(self.updates, [])

    async def test_return_during_mark_read_serializes_later_paging(self):
        screen, pilot = await self.launch()
        self.block_update = True
        try:
            await pilot.press("enter")
            self.assertTrue(await asyncio.to_thread(self.started.wait, 1))
            await pilot.press("escape", "l")
            await pilot.pause()
            self.assertIs(self.app.screen, screen)
            self.assertEqual(self.requests, [1])
        finally:
            self.release.set()
        await self.settle(pilot)
        self.assertEqual(self.requests, [1, 2])
        self.assertEqual(self.updates, [(1, {"archive": 1})])

    async def test_empty_and_short_responses_stop_and_refresh(self):
        self.pages[1] = payload([], pages=1)
        screen, pilot = await self.launch(slim=True, size=(57, 49))
        await pilot.press("l", "enter", "s", "r")
        self.assertEqual(self.requests, [1])
        self.assertEqual(self.updates, [])
        self.pages[1] = payload([1, 2], pages=2, total=3)
        self.pages[2] = payload([3], page=2, pages=2, total=3)
        await pilot.press("R")
        await self.settle(pilot)
        self.screenshot("paging-slim.svg")
        await pilot.resize_terminal(57, 24)
        await pilot.pause()
        label = screen.query_one(Label)
        self.assertLessEqual(label.region.bottom, 24)
        self.assertEqual(screen.query_one(DataTable).max_scroll_x, 0)
        self.screenshot("paging-short.svg")
        await pilot.press("l")
        await self.settle(pilot)
        self.assertEqual(len(screen.entries), 3)
        self.assertIsNone(screen.next_page)
        self.assertEqual(self.updates, [])


if __name__ == "__main__":
    unittest.main()
