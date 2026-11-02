"""Tiingo's end-of-day net asset values for mutual funds as an Open Meridian
data plugin (contract v20): each listed fund's daily NAVs into the
deployment's lake (meridian-design plans/the-lake-prices-the-book, row 14).

It runs its data role class, `Lake` (feed.py's work), on the sidecar it is
launched beside with its catalogue, its storage and its settings
(declaration.py): `meridian.run` (open-meridian 0.35, each role one class)
serves its two pages (page.py), applies the settings, hands it what the
lake wants of it, sets its figures on the heartbeat and starts `Lake.run`
again after a backoff should it fail. It reads each listed fund's last
days at start, when the settings change and every six hours. What Tiingo
answered is kept in the storage the deployment grants (raw.py), and moved
past its window as the settings say. It reads which of its datasets a
deployment admin has licensed, on start and every minute, and the data
role's figures are set on its heartbeat. It holds nothing else.

Its token is the person's own, a secret setting they enter in the dashboard:
sent only to Tiingo, in a header, and never logged, shown or kept.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import meridian

from .declaration import DECLARATION, PORT
from .feed import Feed
from .page import figures, hold, pages
from .raw import RawStore
from .settings import Config, config_from

log = logging.getLogger("tiingo")

#: How often each fund's last days are read, in seconds: every six hours.
CHECK_SECONDS = 6 * 3600
#: How often storage is tended past its window, in seconds: daily.
TEND_SECONDS = 86_400
#: How often the datasets' licences are read again.
LICENCES_SECONDS = 60


async def read_licences(feed: Feed) -> None:
    """Which of its own declared datasets a deployment admin has licensed
    (contract v20, W10.9), for the Datasets page: a dataset with none is
    served by its catalogue's default terms until one is set."""
    answered = await feed.list_datasets()
    feed.status.licensed = frozenset(licence.dataset for licence in answered.licences)


class Lake(Feed):
    """The data role's class: the plugin's work (feed.py), its settings
    applied, and its long-running work -- the funds read, storage tended,
    the licences read -- in `run`."""

    def __init__(self, raw: RawStore) -> None:
        super().__init__(raw)
        self.config = Config()
        self.wake = asyncio.Event()

    async def on_settings(self, delivered: Any) -> None:
        """Each delivery of the settings: the token, sample data and the
        funds, read at once, and the responses' window, tended. `meridian.run`
        applies the first before anything is heard, and watches them again
        should their stream break."""
        config = config_from(delivered.values, delivered.missing)
        self.config = config
        self.configure(config)
        self.wake.set()
        await self.raw.tend(self.plugin, config.window_days, config.past_window, self.now())

    async def run(self) -> None:
        """Each fund's last days read, storage tended daily, and the licences
        read every minute, until stopped."""
        await asyncio.gather(self._check(), self._tend(), self._licences())

    async def _check(self) -> None:
        """Read each fund's last days now, then every six hours, or at once
        when the settings change."""
        while True:
            self.wake.clear()
            try:
                await self.check()
            except meridian.MeridianError as failed:
                # The sidecar refused something a recording needed; say so and
                # keep the schedule rather than spin.
                self.status.error = f"the deployment refused a recording: {failed}"
                log.warning("this check stopped: %s", failed)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.wake.wait(), timeout=CHECK_SECONDS)

    async def _tend(self) -> None:
        while True:
            await asyncio.sleep(TEND_SECONDS)
            config = self.config
            await self.raw.tend(self.plugin, config.window_days, config.past_window, self.now())

    async def _licences(self) -> None:
        """The licences, read on start and every minute."""
        while True:
            try:
                await read_licences(self)
            except meridian.MeridianError as failed:
                log.warning("the datasets' licences were not read this time: %s", failed)
            await asyncio.sleep(LICENCES_SECONDS)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    lake = Lake(RawStore())
    hold(lake)
    # The version's whole declaration (declaration.py): its settings, its
    # pages with the levels each serves and their tools, and its
    # documentation. A version registers exactly what it was uploaded with
    # (contract v25).
    meridian.run(
        declaration=DECLARATION,
        roles=[lake],
        pages=pages,
        port=PORT,
        on_settings=lake.on_settings,
        figures=lambda: figures(lake.status, lake),
    )


if __name__ == "__main__":
    main()
