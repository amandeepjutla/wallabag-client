# Kera (GPT-6 Astra). Created 2026-11-13.
"""Synthetic thread-lifetime checks without credentials or network requests."""
import asyncio
import threading
import unittest

from wallabag.reader_requests import ReaderRequests


class RequestLifetimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_waiter_keeps_running_operation_serial(self):
        requests = ReaderRequests()
        started, release, second_started = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(release.set)
        operations = []

        def first():
            operations.append("first starts")
            started.set()
            release.wait(3)
            operations.append("first finishes")

        def second():
            second_started.set()
            operations.append("second starts")
            return 42

        active = asyncio.create_task(requests.run(first))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            active.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await active
            later = asyncio.create_task(requests.run(second))
            await asyncio.sleep(0.05)
            self.assertFalse(second_started.is_set())
            release.set()
            self.assertEqual(await asyncio.wait_for(later, 1), 42)
            self.assertEqual(operations, ["first starts", "first finishes", "second starts"])
        finally:
            release.set()

    async def test_cancelled_queued_operation_never_runs(self):
        requests = ReaderRequests()
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []

        def first():
            started.set()
            release.wait(3)

        active = asyncio.create_task(requests.run(first))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            queued = asyncio.create_task(requests.run(calls.append, "cancelled"))
            await asyncio.sleep(0.05)
            queued.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await queued
            release.set()
            await active
            await requests.run(calls.append, "accepted")
            self.assertEqual(calls, ["accepted"])
        finally:
            release.set()

    async def test_failure_releases_request_and_preserves_result_arguments(self):
        requests = ReaderRequests()

        def fail():
            raise ValueError("synthetic request failure")

        with self.assertRaisesRegex(ValueError, "synthetic"):
            await requests.run(fail)
        self.assertEqual(await requests.run(lambda value, *, factor: value * factor, 7, factor=3), 21)

    async def test_independent_readers_have_independent_queues(self):
        first, second = ReaderRequests(), ReaderRequests()
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def pending():
            started.set()
            release.wait(3)

        task = asyncio.create_task(first.run(pending))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            self.assertEqual(await asyncio.wait_for(second.run(lambda: 6), 1), 6)
        finally:
            release.set()
            await task

    async def test_cancel_before_release_does_not_need_cancel_handler_to_run(self):
        requests = ReaderRequests()
        started, release, second_started = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def first():
            started.set()
            release.wait(3)

        active = asyncio.create_task(requests.run(first))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            queued = asyncio.create_task(requests.run(second_started.set))
            await asyncio.sleep(0.05)
            queued.cancel()
            release.set()
            # Deliberately hold this event loop after cancellation was requested.
            # A worker-thread queue can otherwise start the cancelled request
            # before the coroutine's CancelledError handler gets a turn.
            self.assertFalse(second_started.wait(0.15))
            with self.assertRaises(asyncio.CancelledError):
                await queued
            await active
            await requests.run(lambda: None)
            self.assertFalse(second_started.is_set())
        finally:
            release.set()

    async def test_cancelled_active_failure_releases_later_request(self):
        requests = ReaderRequests()
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def failure():
            started.set()
            release.wait(3)
            raise ValueError("failed after caller left")

        active = asyncio.create_task(requests.run(failure))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            active.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await active
            release.set()
            self.assertEqual(await asyncio.wait_for(requests.run(lambda: 9), 1), 9)
        finally:
            release.set()
