# Kera (GPT-6.1 Sol). Created 2026-11-11.
# Revised by Kera (GPT-6 Astra): 2026-11-13 (pytest/unittest import compatibility).
"""Narrow article table, scrollable metadata, state and launcher routing."""
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from textual.containers import ScrollableContainer
from textual.widgets import DataTable, Static
from wallabag.tui import ArticleListScreen, ArticleViewScreen, WallabagTUI
if __package__:
    from .test_repair import article, configure
else:
    from test_repair import article, configure


class SlimTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_read_return_resize_and_state(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.ini'
            configure(config)
            item = article()
            item['title'] = 'A full article title with enough words to require truncation in the list'
            item['tags'] = [{'id': 1, 'label': 'Synthetic tag'}]
            updates = []
            with patch('wallabag.tui.GetListEntries.request', return_value=SimpleNamespace(response={'_embedded': {'items': [item]}})), \
                 patch('wallabag.tui.GetEntry.request', return_value=SimpleNamespace(response=item)), \
                 patch('wallabag.tui.UpdateEntry.request', side_effect=lambda: updates.append('update')):
                app = WallabagTUI(str(config), slim=True)
                async with app.run_test(size=(57, 49)) as pilot:
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    table = app.screen.query_one(DataTable)
                    self.assertEqual([c.key.value for c in table.ordered_columns], ['status', 'title', 'time'])
                    self.assertGreaterEqual(table.columns['title'].width, 35)
                    self.assertEqual(table.max_scroll_x, 0)
                    self.assertEqual(updates, [])
                    if output := os.environ.get('SLIM_QA_DIR'):
                        app.save_screenshot('wallabag-list.svg', path=output)
                    await pilot.press('enter')
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertIsInstance(app.screen, ArticleViewScreen)
                    self.assertEqual(len(updates), 1)
                    pane = app.screen.query_one('#content_scroll', ScrollableContainer)
                    self.assertGreater(pane.size.height, 40)
                    self.assertEqual(pane.max_scroll_x, 0)
                    self.assertIn('Synthetic tag', str(app.screen.query_one('#article_meta', Static).renderable))
                    self.assertIn('Beginning [test]', str(app.screen.query_one('#article_content', Static).renderable))
                    self.assertNotIn(item['title'], str(app.screen.query_one('#article_content', Static).renderable))
                    if output:
                        app.save_screenshot('wallabag-reading.svg', path=output)
                    await pilot.press('end')
                    await pilot.pause()
                    self.assertGreater(pane.scroll_y, 0)
                    await pilot.resize_terminal(57, 39)
                    await pilot.press('escape')
                    await pilot.pause()
                    self.assertIsInstance(app.screen, ArticleListScreen)
                    self.assertEqual(table.max_scroll_x, 0)
                    self.assertEqual(table.get_cell('1', 'status'), 'R ')
                    await pilot.press('q')
                    self.assertFalse(app.is_running)


class LauncherTests(unittest.TestCase):
    def test_slim_routes_to_reader_and_cli_stays_available(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'pixi'
            fake.write_text('#!/bin/sh\n# Kera (GPT-6.1 Sol). Created 2026-11-11.\nprintf "%s\\n" "$@"\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ['PATH'], WALLABAG_PROJECT=str(project))
            for args in (['--slim'], ['--tui', '--slim']):
                result = subprocess.run([str(project / 'wallabag'), *args, '--config', 'fixture.ini'],
                                        env=env, text=True, capture_output=True, check=True)
                self.assertIn('wallabag-tui\n--slim\n--config\nfixture.ini', result.stdout)
            result = subprocess.run([str(project / 'wallabag'), 'list'], env=env,
                                    text=True, capture_output=True, check=True)
            self.assertIn('--executable\nwallabag\nlist', result.stdout)
