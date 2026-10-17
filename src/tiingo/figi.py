"""OpenFIGI's mapping: each fund's ticker to its FIGIs, under the
deployment's access (decision 64, 2026-10-16).

Tiingo names a fund by its ticker alone, and a ticker is no open identifier:
from contract v24 a fund resolved by a vendor's symbol alone stays a local
record, which the lake never wants (W3.7, W10.6). So before a fund is
resolved, its ticker is mapped through OpenFIGI's mapping API
(https://www.openfigi.com/api), and each FIGI it answers is stated on the
resolve beside Tiingo's symbol (`figi`, `composite_figi`,
`share_class_figi`, the schemes' approved names), so the fund meets the
platform's record for it.

- One call: `POST /v3/mapping`, a list of jobs, each `{"idType": "TICKER",
  "idValue": <ticker>, "exchCode": "US", "securityType2": "Mutual Fund"}`;
  the answer a list in the jobs' order, each `{"data": [...]}` (each
  instrument's `figi`, `compositeFIGI`, `shareClassFIGI`), `{"warning":
  ...}` where none is found, or `{"error": ...}`.
- **The deployment's access.** OpenFIGI answers without a key at its lower
  limits (25 requests a minute, 10 jobs a request); with the deployment's
  own key, the optional secret setting `openfigi_api_key`, sent in the
  `X-OPENFIGI-APIKEY` header and nowhere else, at its higher ones (25
  requests in 6 seconds, 100 jobs). Its terms are the deployment's, as
  Tiingo's are.
- **Never guessed.** A ticker OpenFIGI answers with no instrument, or with
  more than one distinct FIGI, maps to none, and the fund is resolved by
  Tiingo's symbol alone, as before.

`SyntheticOpenFigi` answers for sample data, never calling OpenFIGI: VIGIX
and VTSAX by FIGIs invented for the e2e, the ones its stand-in platform is
told it holds, and none for any other ticker.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from meridian.plugin.v1 import operations_pb2 as ops

URL = "https://api.openfigi.com/v3/mapping"
USER_AGENT = "meridian-tiingo (+https://github.com/open-meridian/plugin-tiingo)"
TIMEOUT = 30.0
MOST_BYTES = 4 * 1024 * 1024
#: Jobs in one request, without a key and with one.
JOBS_KEYLESS = 10
JOBS_KEYED = 100
#: The least time between two requests, in seconds: inside 25 a minute
#: without a key, and 25 in six seconds with one.
SPACING_KEYLESS = 2.5
SPACING_KEYED = 0.3


@dataclass(frozen=True)
class Figis:
    """What OpenFIGI answered for one ticker: its FIGI, its composite FIGI and
    its share class's, each empty where not stated."""

    figi: str
    composite: str = ""
    share_class: str = ""

    def identifiers(self) -> list[ops.Identifier]:
        """Each as a resolve states it, by its scheme's approved name."""
        return [
            ops.Identifier(scheme=scheme, value=value)
            for scheme, value in (
                ("figi", self.figi),
                ("composite_figi", self.composite),
                ("share_class_figi", self.share_class),
            )
            if value
        ]


class Unmapped(Exception):
    """OpenFIGI could not be asked, or refused: its status, or why."""


class OpenFigi(Protocol):
    mode: str

    async def map(self, tickers: Sequence[str]) -> dict[str, Figis | None]: ...


def figis_of(answer: Any) -> Figis | None:
    """One job's answer as one instrument's FIGIs: None where it found none,
    or more than one distinct FIGI, which is never guessed between."""
    if not isinstance(answer, dict):
        return None
    found = [each for each in answer.get("data") or [] if isinstance(each, dict)]
    distinct = {str(each.get("figi") or "") for each in found} - {""}
    if len(distinct) != 1:
        return None
    first = next(each for each in found if each.get("figi"))
    return Figis(
        figi=str(first.get("figi") or ""),
        composite=str(first.get("compositeFIGI") or ""),
        share_class=str(first.get("shareClassFIGI") or ""),
    )


def jobs(tickers: Sequence[str]) -> list[dict[str, str]]:
    return [
        {"idType": "TICKER", "idValue": ticker, "exchCode": "US", "securityType2": "Mutual Fund"}
        for ticker in tickers
    ]


class LiveOpenFigi:
    """OpenFIGI's mapping API, with the deployment's key where it gave one."""

    mode = "live"

    def __init__(self, key: str = "") -> None:
        self._key = key
        self._last = 0.0
        self._lock = asyncio.Lock()

    @property
    def keyed(self) -> bool:
        return bool(self._key)

    async def map(self, tickers: Sequence[str]) -> dict[str, Figis | None]:
        mapped: dict[str, Figis | None] = {}
        size = JOBS_KEYED if self._key else JOBS_KEYLESS
        for start in range(0, len(tickers), size):
            batch = list(tickers[start : start + size])
            answers = await self._post(jobs(batch))
            if not isinstance(answers, list) or len(answers) != len(batch):
                raise Unmapped("OpenFIGI answered a list not in the jobs' order")
            mapped.update(zip(batch, (figis_of(each) for each in answers), strict=True))
        return mapped

    async def _post(self, body: list[dict[str, str]]) -> Any:
        async with self._lock:
            spacing = SPACING_KEYED if self._key else SPACING_KEYLESS
            wait = self._last + spacing - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await asyncio.to_thread(self._send, body)
            finally:
                self._last = time.monotonic()

    def _send(self, body: list[dict[str, str]]) -> Any:
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self._key:
            headers["X-OPENFIGI-APIKEY"] = self._key
        request = urllib.request.Request(
            URL, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answered:
                return json.loads(answered.read(MOST_BYTES))
        except urllib.error.HTTPError as refused:
            raise Unmapped(f"OpenFIGI answered {refused.code}") from None
        except (OSError, ValueError) as failed:
            raise Unmapped(f"OpenFIGI could not be asked: {type(failed).__name__}") from None


#: The synthetic mapping: each FIGI invented, the e2e's stand-in platform's.
SYNTHETIC = {
    "VIGIX": Figis("BBG00E2EVIGX"),
    "VTSAX": Figis("BBG00E2EVTSX"),
}


class SyntheticOpenFigi:
    """OpenFIGI for sample data: never called; the invented FIGIs above."""

    mode = "synthetic"

    async def map(self, tickers: Sequence[str]) -> dict[str, Figis | None]:
        return {ticker: SYNTHETIC.get(ticker.upper()) for ticker in tickers}


def openfigi(synthetic: bool, key: str) -> OpenFigi:
    """OpenFIGI, synthetic for sample data, else live: with the deployment's
    key where it gave one, at OpenFIGI's keyless limits where it gave none."""
    return SyntheticOpenFigi() if synthetic else LiveOpenFigi(key)
