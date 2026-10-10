# meridian-tiingo

An [Open Meridian](https://open-meridian.com) plugin that puts mutual funds'
daily net asset values from [Tiingo](https://www.tiingo.com) into a
deployment's lake: each fund you list, its NAV for each business day, so a
reporting plugin can value a fund no exchange prices, such as VIGIX. It holds
the `dgm` role. This is release 0.1.0, not released yet. How to set it up and
use it is in [docs/](docs/README.md); how a plugin like it is built is
documented at [open-meridian.dev](https://open-meridian.dev).

It is built on the SDK it pins, `open-meridian==0.22.0`, which declares
contract v18, the lake prices the book (meridian-design
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
  Funds setting names, or its ticker as Tiingo's symbol, a miss reported.
- **Every response kept** as received, without the token, in the storage the
  deployment grants, and named by each row read from it.

Its pages, under Manage alone, show how it reaches Tiingo and what it serves,
never a NAV and never the token: **Connection** (`read_connection`) and
**Datasets** (`read_datasets`), each the same through the deployment's MCP.

## Settings

- **API token** (`tiingo_api_token`), secret: your own Tiingo account's
  token, entered by you in the dashboard. Sent only to Tiingo, in a header.
- **Funds** (`funds`), a table: each fund's ticker, and optionally the
  deployment's record for it (the one your custodian's positions name).
- **Synthetic mode**, on a development deployment: invented responses, no
  token.

## The live check, for the person who holds the Tiingo account

Nothing here has called Tiingo: the tests and the e2e use invented responses,
and no token was ever handled by its builders. To check it live:

1. In the deployment's dashboard, open this plugin's **Settings**.
2. Enter your token in **API token** (from your Tiingo account's API page).
3. Under **Funds**, add `VIGIX`, and pick its instrument where your
   custodian's positions already name one. Save.
4. Open **Connection**: within a minute it says "Tiingo read", the token
   "Set", a few requests this hour. Open **Datasets**: VIGIX is a mutual fund,
   resolved to an instrument, its latest recorded day the last business day.
   Or ask an agent for `read_datasets` through the deployment's MCP.
5. On the deployment's **Data sources** page, license `<instance>:daily` as
   your terms say, and entitle your reporting plugin to it.

If Connection says Tiingo refused the token, enter it again; if it says the
limit was reached, the plugin waits and tries again.

## Checking it

    make ci-local                                  # lint, tests, plugin check, image, e2e: the pre-push gate
    make preview SHOTS=<dir>                       # each page in a browser with the kit, at 1440x900 and 390x844

`make e2e` runs it on core's plugin harness (core b1b8420) beside a reading
plugin, Tiingo's API unreachable: waiting with no token, then in synthetic
mode with VIGIX, VOO and NOSUCH listed, VIGIX alone served, its NAVs read
back, a past day wanted and recorded, a day with no NAV yet declined, both
tools answering what the pages show, and a new container recording nothing
twice.

**The `dgm` suite.** `tests/test_suite.py` runs the SDK's suite on the
plugin's own conversion. A NAV-only source presents five of its twelve
cases; the other seven ask for a close, a bar, an FX rate, a stablecoin or a
venue, which a fund's NAV is not, and the SDK's runner lets only a
closed-list case be not presented, so by its rule the plugin is short of the
suite and not verified; the test holds it to exactly that.

**CI is red until open-meridian 0.22.0 is on PyPI** and its base image on
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
