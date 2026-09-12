# Kera (GPT-6 Astra)
# Created: 2026-09-12
"""Keep command tests independent of terminal spinner threads."""
import pytest

from wallabag import wclick


@pytest.fixture(autouse=True)
def stop_command_spinner():
    yield
    # Some command-level tests call a prompt without its outer CLI context.
    # The prompt restarts the spinner, so teardown must join its thread.
    if wclick.SPINNER is not None:
        wclick.SPINNER.stop()
        wclick.SPINNER = None
