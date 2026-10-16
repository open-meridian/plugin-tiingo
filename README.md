# meridian-tiingo

An [Open Meridian](https://open-meridian.com) plugin that puts mutual funds'
daily net asset values from [Tiingo](https://www.tiingo.com) into a
deployment's lake: each fund you list, its NAV for each business day, so a
reporting plugin can value a fund no exchange prices, such as VIGIX. It holds
the `data` role, a data plugin. This is release 0.5.0, not released yet. How to set it up and
use it is in [docs/](docs/README.md); how a plugin like it is built is
documented at [open-meridian.dev](https://open-meridian.dev).

It is built on the SDK it pins, `open-meridian==0.29.0`, which declares
contract v25 (not yet on PyPI: its whole declaration, and docs/, which a deployment shows on its Documentation tab; each fund's ticker mapped to its FIGIs through OpenFIGI); its work is the lake prices the book (meridian-design
`plans/the-lake-prices-the-book.md`, row 14).

## What it records

- **One dataset, `<instance>:daily`:** NAVs, each fund's last days pushed
  every six hours and any past day pulled when the lake wants it; daily; New
  York's day, ending at 16:00; no venue; one person's terms.
- **A fund's NAV, kind `nav`,** for its business date, in US dollars, exact:
  made a decimal from the number's text in Tiingo's response, never a float.
  Tiingo gives a fund's NAV as the day's close, after midnight New York time.
- **Only mutual funds.** A listed ticker Tiingo files under `NMFQS` is served;
  an ETF or a stock is shown as not a mutual fund and not recorded (its closes
  are the equity datasets'); a ticker Tiingo does not know is shown as not
  found.
- **Each fund resolved** to the deployment's record: the one its row in the
  Funds setting names, or its ticker as Tiingo's symbol beside each FIGI
  OpenFIGI maps the ticker to under the deployment's access (`figi.py`,
  decision 64), so it meets the platform's record, a miss reported;
  every resolve as of the moment it is asked. No currency is resolved here:
  a NAV names its dollars by code, and core resolves the code to the
  platform master's currency, pulled, never a stub the plugin minted.
- **Every response kept** as received, without the token, in the storage the
  deployment grants, and named by each row read from it.

Its pages, under Manage alone, are the data role's, the same on every data
plugin, and show how it reaches Tiingo and what it serves, never a NAV and
never the token: **Connection** (`read_connection`) and **Datasets**
(`read_datasets`), each the same through the deployment's MCP, Datasets
saying whether a deployment admin has licensed the dataset. The data role's
figures are on its Summary. It does not stream, so it has no restart's gap
to backfill.

## Settings

- **API token** (`tiingo_api_token`), secret: your own Tiingo account's
  token, entered by you in the dashboard. Sent only to Tiingo, in a header.
- **OpenFIGI API key** (`openfigi_api_key`), secret and optional: the
  deployment's own OpenFIGI key, for OpenFIGI's higher limits; without it,
  each ticker is mapped at OpenFIGI's keyless limits. Sent only to OpenFIGI,
  in a header. Tests and sample data never call OpenFIGI.
- **Funds** (`funds`), a table: each fund's ticker, and optionally the
  deployment's record for it (the one your custodian's positions name).
  A fund your book already holds from a custodian needs no row: when a
  reader asks for its NAV, the plugin reads its record, and where the
  record carries a ticker Tiingo files as a mutual fund, serves it from then
  on, up to the same 100 funds in all.
- **Sample data** (`sample_data`, `synthetic` until 0.2.0), on a
  development deployment: invented responses, no token.

## The live check, for the person who holds the Tiingo account

Nothing here has called Tiingo: the tests and the e2e use invented responses,
and no token was ever handled by its builders. To check it live:

1. In the deployment's dashboard, open this plugin's **Settings**.
2. Enter your token in **API token** (from your Tiingo account's API page).
3. Under **Funds**, add `VIGIX`, and pick its instrument where your
   custodian's positions already name one. Save.
4. Open **Connection**: within a minute its Mode says Live, the API token
   "set", a few requests this hour; the Summary's Connection figure says
   Answering. Open **Datasets**: VIGIX is a mutual fund,
   resolved to an instrument, its latest recorded day the last business day.
   Or ask an agent for `read_datasets` through the deployment's MCP.
5. On the deployment's **Data sources** page, license `<instance>:daily` as
   your terms say, and entitle your reporting plugin to it. Datasets says it
   is licensed within a minute.

If Connection says Tiingo refused the token, enter it again; if it says the
limit was reached, the plugin waits and tries again.

## Checking it

    make ci-local                                  # lint, tests, plugin check, image, e2e: the pre-push gate
    make preview SHOTS=<dir>                       # each page in a browser with the kit, at 1440x900 and 390x844

`make e2e` runs it on core's plugin harness (core v20, local) beside a
reading plugin, Tiingo's API unreachable: no key said with no token, then on
sample data with VIGIX, VOO and NOSUCH listed,
VIGIX alone served, its NAVs read back, a past day wanted and recorded, a
day with no NAV yet declined, VTSAX -- listed nowhere, known only by a
custodian's CUSIP and symbol -- read from its record and its NAV recorded
for the reader, both tools answering what the pages show, and a new
container recording nothing twice and reading its licence on start.

**The data suite.** `tests/test_suite.py` runs the SDK's suite on the
plugin's own conversion, and it passes: seven cases are presented (and the
SDK answers contract v24's replacement and template-catalogue cases), a fund
known only by another source's identifiers and its dataset's licences
among them; every other case is about a kind of data a fund's NAV is not
(a close, a bar, an FX rate, a crypto asset, a venue, trades, quotes), and
is not presented, with why, as the suite lets it. So are contract v22's
calendar cases: the plugin records each NAV on the business date Tiingo
states, and never reads a settlement calendar or asks for a settlement date;
and contract v23's outcomes, a fund being no event contract. From 0.5.0 the
dataset names the platform's US equity venues (NYSE markets) calendar, so the
lake flags a NAV dated on a day it says is closed.

**CI is red until open-meridian 0.29.0 is on PyPI** and its base image on
ghcr.io: the runners install the pin from there. Locally the Makefile builds
both from the sibling meridian-python checkout.

## The terms, summarised

Not legal advice; read Tiingo's own terms and pricing before relying on
them, as they change.

- **Your own account, your own agreement.** You use Tiingo under your own
  account and its terms; the plugin calls it with your token.
- **Free and Power plans are for internal and personal use,** with no
  redistribution. So the dataset's default licence is one person's terms
  (`personal_use`): kept, used to value your own book and shown to you. The
  deployment's Data sources page warns when more than one person may read a
  dataset licensed so. A firm's use needs Tiingo's commercial terms.
- **The free plan's limits,** as Tiingo states them: 50 requests an hour,
  1,000 a day, 500 symbols a month. The plugin keeps inside them.
- **NAVs after midnight New York time.** A fund's NAV for a day arrives the
  night after; each NAV shows its date.
- **No endorsement.** This project is not affiliated with or endorsed by
  Tiingo.

## Licence

Apache-2.0 (LICENSE, NOTICE). The responses under `src/tiingo/synthetic/` are
synthetic, every value invented.
