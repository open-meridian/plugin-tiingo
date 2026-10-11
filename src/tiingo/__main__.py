"""Tiingo's end-of-day net asset values for mutual funds as an Open Meridian
data plugin (contract v20): each listed fund's daily NAVs into the
deployment's lake (meridian-design plans/the-lake-prices-the-book, row 14).

It connects to the sidecar it is launched beside with its catalogue, its
storage and its settings (declaration.py), serves its two pages (page.py),
hears what the lake wants of it, and reads each listed fund's last days at
start, when the settings change and every six hours (feed.py). What Tiingo
answered is kept in the storage the deployment grants (raw.py), and moved
past its window as the settings say. It reads which of its datasets a
deployment admin has licensed, on start and every minute, and reports the
data role's figures on its heartbeat. It holds nothing else.

Its token is the person's own, a secret setting they enter in the dashboard:
sent only to Tiingo, in a header, and never logged, shown or kept.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from typing import Any

import meridian

from .declaration import DECLARATION
from .feed import Feed
from .page import TITLE, figures, hold, pages
from .raw import RawStore
from .settings import DECLARED, Config, config_from

log = logging.getLogger("tiingo")

#: The port the pages are served on, beside the sidecar.
PORT = 8000
#: How often each fund's last days are read, in seconds: every six hours.
CHECK_SECONDS = 6 * 3600
#: How long before a broken settings stream is asked again, in seconds.
RETRY_SECONDS = 5
#: How often storage is tended past its window, in seconds: daily.
TEND_SECONDS = 86_400
#: How often the datasets' licences are read again, and the figures set.
LICENCES_SECONDS = 60


async def watch_settings(
    plugin: meridian.Plugin, feed: Feed, held: list[Config], wake: asyncio.Event
) -> None:
    """Apply each delivery of the settings: the token, sample data and the
    funds, read at once, and the responses' window, tended. A stream that
    breaks -- the deployment not serving its configuration yet at a first
    start, or restarting -- is asked again after a pause, and delivers the
    settings whole."""
    while True:
        try:
            async for delivered in plugin.settings():
                config = config_from(delivered.values, delivered.missing_required)
                held[0] = config
                feed.configure(config)
                wake.set()
                await feed.raw.tend(plugin, config.window_days, config.past_window, feed.now())
        except Exception as broken:  # noqa: BLE001 - a broken stream, asked again
            log.warning("the settings were not delivered (%s); asking again", broken)
        await asyncio.sleep(RETRY_SECONDS)


async def check(feed: Feed, wake: asyncio.Event) -> None:
    """Read each fund's last days once the settings have come, then every six
    hours, or at once when the settings change."""
    await wake.wait()
    while True:
        wake.clear()
        try:
            await feed.check()
        except meridian.MeridianError as failed:
            # The sidecar refused something a recording needed; say so and
            # keep the schedule rather than spin.
            feed.status.error = f"the deployment refused a recording: {failed}"
            log.warning("this check stopped: %s", failed)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(wake.wait(), timeout=CHECK_SECONDS)


async def tend(plugin: meridian.Plugin, feed: Feed, held: list[Config]) -> None:
    while True:
        await asyncio.sleep(TEND_SECONDS)
        config = held[0]
        await feed.raw.tend(plugin, config.window_days, config.past_window, feed.now())


async def read_licences(plugin: Any, feed: Feed) -> None:
    """Which of its own declared datasets a deployment admin has licensed
    (contract v20, W10.9), for the Datasets page: a dataset with none is
    served by its catalogue's default terms until one is set."""
    answered = await plugin.list_datasets()
    feed.status.licensed = frozenset(licence.dataset for licence in answered.licences)


async def licences(plugin: meridian.Plugin, feed: Feed) -> None:
    """The licences, read on start and every minute; and the data role's
    figures, set for the next heartbeat."""
    while True:
        try:
            await read_licences(plugin, feed)
        except meridian.MeridianError as failed:
            log.warning("the datasets' licences were not read this time: %s", failed)
        plugin.figures = figures(feed.status, feed)
        await asyncio.sleep(LICENCES_SECONDS)


def _said(task: asyncio.Task[None]) -> None:
    """A task that ended on an error says so, rather than ending unseen."""
    if not task.cancelled() and task.exception() is not None:
        log.error("%s stopped", task.get_name(), exc_info=task.exception())


async def run() -> None:
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(stop, stopped.set)

    async with await meridian.connect(
        # Two pages, under Manage alone: a data plugin's pages are its admin's.
        interface=meridian.Interface(port=PORT, title=TITLE, pages=pages),
        settings=DECLARED,
        # Its catalogue, its storage and its settings (contract v18).
        declaration=DECLARATION,
    ) as plugin:
        log.info("registered as %s, roles %s", plugin.identity.instance_id, plugin.identity.roles)
        feed = Feed(plugin, RawStore())
        hold(feed)
        held = [Config()]
        wake = asyncio.Event()
        server = pages.serve(plugin, PORT)
        log.info("serving its pages on 127.0.0.1:%d", PORT)
        tasks = [
            asyncio.create_task(
                plugin.receive(observations_wanted=feed.on_want, want_withdrawn=feed.on_withdrawn)
            ),
            asyncio.create_task(watch_settings(plugin, feed, held, wake)),
            asyncio.create_task(check(feed, wake)),
            asyncio.create_task(tend(plugin, feed, held)),
            asyncio.create_task(licences(plugin, feed)),
        ]
        for task in tasks:
            task.add_done_callback(_said)
        await stopped.wait()
        log.info("stopping")
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        server.shutdown()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
