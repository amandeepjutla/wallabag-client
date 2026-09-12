# Kera (GPT-6-Astra)
# Created: 2026-09-11
"""Offline regressions for credential recovery and the terminal reader."""
import asyncio
import contextlib
import io
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests
from textual.containers import ScrollableContainer
from textual.widgets import DataTable, Label, Static

from wallabag.api.api import Api, RequestException, Response, Verbs
from wallabag.api.api_token import ApiToken
from wallabag.api.get_entry import GetEntry
from wallabag.config import Configs, Options, Sections
from wallabag.entry import Entry
from wallabag.tui import ArticleListScreen, ArticleViewScreen, WallabagTUI


def article(entry_id=1, read=False):
    return dict(id=entry_id, title='A [bold]literal[/bold] title',
                content='<p>Beginning [test]</p>' + '<p>Reading paragraph.</p>' * 150,
                url='https://example.org/article', is_archived=int(read), is_starred=0,
                reading_time=5, tags=[])


def configure(path):
    c = Configs(str(path))
    for s, k, v in [('api', 'serverurl', 'https://example.org'),
                    ('api', 'username', 'reader'), ('api', 'password', 'test-password'),
                    ('oauth2', 'client', 'test-client'), ('oauth2', 'secret', 'test-secret')]:
        c.set(s, k, v)
    c.save()
    return c


class ConfigAndApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.ini'

    def test_credentials_survive_hostname_change_and_reload(self):
        with patch('wallabag.config.socket.gethostname', return_value='Hyperborea.local'):
            configure(self.path)
        with patch('wallabag.config.socket.gethostname', return_value='different-host.local'):
            c = Configs(str(self.path))
            self.assertEqual(c.get('api', 'password'), 'test-password')
            self.assertEqual(c.get('oauth2', 'secret'), 'test-secret')
            c.set('api', 'password', 'new-password')
            c.save()
            self.assertEqual(Configs(str(self.path)).get('api', 'password'), 'new-password')

    def test_legacy_config_and_explicit_hostname_recovery(self):
        with patch('wallabag.config.socket.gethostname', return_value='Hyperborea.local'):
            c = configure(self.path)
            c.config.remove_option('api', Options.ENCRYPTION_HOSTNAME)
            c.save()
        with patch('wallabag.config.socket.gethostname', return_value='hyperborea.local'):
            c = Configs(str(self.path))
            with self.assertRaisesRegex(ValueError, 'Could not decrypt'):
                c.get('api', 'password')
            c.set('api', Options.ENCRYPTION_HOSTNAME, 'Hyperborea.local')
            self.assertEqual(c.get('api', 'password'), 'test-password')
            self.assertEqual(c.get('oauth2', 'secret'), 'test-secret')

    def test_successful_legacy_decryption_pins_hostname(self):
        c = configure(self.path)
        c.config.remove_option('api', Options.ENCRYPTION_HOSTNAME)
        self.assertEqual(c.get('api', 'password'), 'test-password')
        self.assertTrue(c.config.has_option('api', Options.ENCRYPTION_HOSTNAME))

    def test_token_credentials_in_post_body(self):
        c = configure(self.path)
        def post(url, **kwargs):
            self.assertIsNone(kwargs['params'])
            self.assertEqual(kwargs['data']['password'], 'test-password')
            self.assertEqual(kwargs['timeout'], (10, 30))
            return SimpleNamespace(status_code=200, text='{"access_token":"test"}',
                                   content=b'', headers={'Content-Type':'application/json; charset=utf-8'})
        with patch.dict(Api.REQUEST_METHODS, {Verbs.POST: post}):
            self.assertEqual(ApiToken(c).request().response['access_token'], 'test')

    def test_timeout_is_readable_and_contains_no_credentials(self):
        c = configure(self.path)
        def timeout(*args, **kwargs):
            raise requests.Timeout('test-password')
        with patch.dict(Api.REQUEST_METHODS, {Verbs.POST: timeout}):
            with self.assertRaises(RequestException) as error:
                ApiToken(c).request()
            self.assertIn('timed out', str(error.exception))
            self.assertNotIn('test-password', str(error.exception))

    def test_non_json_error_does_not_crash(self):
        r = Response(401, text='<html>failure</html>', content_type='text/html')
        self.assertTrue(r.has_error())
        self.assertIn('invalid error response', r.error_text)

    def test_metadata_without_content_and_null_title(self):
        item = article()
        del item['content']
        item['title'] = None
        entry = Entry(item)
        self.assertEqual(entry.content, '')
        self.assertEqual(entry.title, item['url'])


class ReaderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.ini'
        configure(self.path)
        self.items = [article(1), article(2, read=True)]
        self.updates = []
        self.fail_updates = False
        self.patches = [
            patch('wallabag.tui.GetListEntries.request', side_effect=self.list_entries),
            patch('wallabag.tui.GetEntry.request', autospec=True, side_effect=self.get_entry),
            patch('wallabag.tui.UpdateEntry.request', autospec=True, side_effect=self.update),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.app = WallabagTUI(str(self.path))

    def list_entries(self):
        return SimpleNamespace(response={'_embedded': {'items': self.items}})

    def get_entry(self, api):
        return SimpleNamespace(response=next(i for i in self.items if i['id'] == api.entry_id))

    def update(self, api):
        if self.fail_updates:
            raise RequestException('server unavailable')
        self.updates.append((api.entry_id, api._get_data()))
        return SimpleNamespace(response={})

    async def settle(self, pilot):
        await self.app.workers.wait_for_complete()
        await pilot.pause()

    async def test_enter_read_scroll_return_and_quit(self):
        async with self.app.run_test(size=(100, 30)) as pilot:
            await self.settle(pilot)
            table = self.app.screen.query_one(DataTable)
            self.assertEqual(table.row_count, 2)
            self.assertEqual(table.cursor_type, 'row')
            self.assertIn('[bold]', str(table.get_cell('1', 'title')))
            await pilot.press('enter')
            await self.settle(pilot)
            self.assertIsInstance(self.app.screen, ArticleViewScreen)
            self.assertEqual(len(self.app.screen_stack), 3)
            content = self.app.screen.query_one('#article_content', Static)
            self.assertIn('Beginning [test]', str(content.renderable))
            scroll = self.app.screen.query_one('#content_scroll', ScrollableContainer)
            self.assertGreater(scroll.size.height, 10)
            self.assertGreater(scroll.max_scroll_y, 0)
            await pilot.press('end')
            await pilot.pause(0.3)
            self.assertGreater(scroll.scroll_y, 0)
            await pilot.press('home')
            await pilot.pause(0.3)
            self.assertEqual(scroll.scroll_y, 0)
            await pilot.press('q')
            await pilot.pause()
            self.assertIsInstance(self.app.screen, ArticleListScreen)
            self.assertEqual(table.get_cell('1', 'status'), 'R ')
            self.assertEqual(self.updates, [(1, {'archive': 1})])
            await pilot.press('q')
        self.assertEqual(self.app.return_code, 0)

    async def test_navigation_toggle_and_failed_toggle(self):
        async with self.app.run_test(size=(80, 24)) as pilot:
            await self.settle(pilot)
            table = self.app.screen.query_one(DataTable)
            label = self.app.screen.query_one(Label)
            self.assertGreater(label.region.height, 0)
            self.assertLess(label.region.bottom, self.app.size.height)
            await pilot.press('j', 's')
            await self.settle(pilot)
            self.assertEqual(table.cursor_row, 1)
            self.assertEqual(table.get_cell('2', 'status'), 'R*')
            await pilot.press('r')
            await self.settle(pilot)
            self.assertEqual(table.get_cell('2', 'status'), 'N*')
            self.fail_updates = True
            await pilot.press('r')
            await self.settle(pilot)
            self.assertEqual(table.get_cell('2', 'status'), 'N*')
            self.assertIn('Could not update', str(label.renderable))
            await pilot.press('k', 'o')
            await self.settle(pilot)
            self.assertIsInstance(self.app.screen, ArticleViewScreen)
            self.assertIn('could not mark as read',
                          str(self.app.screen.query_one('#article_meta', Static).renderable))
            await pilot.press('escape')
            self.assertEqual(table.cursor_row, 0)

    async def test_empty_list(self):
        self.items = []
        async with self.app.run_test() as pilot:
            await self.settle(pilot)
            await pilot.press('enter', 'r', 's')
            await self.settle(pilot)
            self.assertIsInstance(self.app.screen, ArticleListScreen)
            self.assertEqual(self.updates, [])
            self.assertIn('No articles', str(self.app.screen.query_one(Label).renderable))

    async def test_title_fills_pane_on_startup_and_resize(self):
        title = 'What Isaac Asimov Reveals About Living with A.I. | The New Yorker'
        self.items = [dict(article(i), title=title) for i in range(67)]
        async with self.app.run_test(size=(118, 40)) as pilot:
            await self.settle(pilot)
            table = self.app.screen.query_one(DataTable)
            # Check rendered text as well as column metadata: stale cell caches
            # previously hid the title even with plenty of empty pane space.
            self.assertIn(title, table.render_line(1).text)
            table.move_cursor(row=30)
            await pilot.pause()
            for width in (80, 160, 60, 118):
                await pilot.resize_terminal(width, 40)
                await pilot.pause()
                with self.subTest(width=width):
                    self.assertEqual(table.cursor_row, 30)
                    self.assertEqual(table.row_count, 67)
                    self.assertEqual(table.virtual_size.width,
                                     table.scrollable_content_region.width)
                    self.assertEqual(table.max_scroll_x, 0)
                    self.assertGreater(table.columns['title'].width, 20)
                    rendered = table.render_line(1).text
                    if width >= 118:
                        self.assertIn(title, rendered)
                    else:
                        self.assertIn('…', rendered)
                    self.assertIn('5m', rendered)

    async def test_empty_table_also_fills_pane(self):
        self.items = []
        async with self.app.run_test(size=(118, 40)) as pilot:
            await self.settle(pilot)
            table = self.app.screen.query_one(DataTable)
            self.assertEqual(table.virtual_size.width,
                             table.scrollable_content_region.width)
            self.assertEqual(table.max_scroll_x, 0)

    async def test_failed_article_stays_unread(self):
        with patch('wallabag.tui.GetEntry.request', side_effect=RequestException('offline')):
            async with self.app.run_test() as pilot:
                await self.settle(pilot)
                await pilot.press('enter')
                await self.settle(pilot)
                self.assertIn('Error loading article',
                              str(self.app.screen.query_one('#article_content', Static).renderable))
                self.assertEqual(self.updates, [])
                self.assertFalse(self.app.entries[0].read)

    async def test_startup_failure_reports_nonzero_and_message(self):
        output = io.StringIO()
        with patch('wallabag.tui.GetListEntries.request', side_effect=RequestException('offline')):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                async with self.app.run_test() as pilot:
                    await self.settle(pilot)
            self.assertEqual(self.app.return_code, 1)
            self.assertIn('offline', output.getvalue())

    async def test_missing_configuration(self):
        app = WallabagTUI(str(Path(self.temp.name) / 'absent.ini'))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            async with app.run_test() as pilot:
                await pilot.pause()
        self.assertEqual(app.return_code, 1)
        self.assertIn('wallabag config', output.getvalue())

    async def test_loading_does_not_block_quit(self):
        gate = threading.Event()
        def blocked():
            gate.wait(3)
            return self.list_entries()
        try:
            with patch('wallabag.tui.GetListEntries.request', side_effect=blocked):
                async with self.app.run_test() as pilot:
                    await asyncio.wait_for(pilot.press('q'), timeout=1)
                self.assertEqual(self.app.return_code, 0)
        finally:
            gate.set()


if __name__ == '__main__':
    unittest.main()
