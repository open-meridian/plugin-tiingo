# Changelog

## 0.8.0

On open-meridian 0.32.2, contract v27: the NAVs' delay declared, and the
suite's v27 cases mapped or not presented honestly. What the plugin records
is unchanged.

- **The declared delay** (contract v27, `declared_delay_ns`): the `daily`
  dataset declares eight hours, from 16:00 New York, when a fund strikes its
  NAV, to midnight, when Tiingo has it ("Mutual Fund NAVs are available
  after 12 AM EST", Tiingo's end-of-day documentation). The lake judges a
  NAV's staleness against the delay plus its ceiling.
- **The bounded lake query is no longer faked.**
  `queries-the-lake-within-bounds` is about trades from contract v27, and
  the plugin records none, so it is not presented ("it records no trades")
  rather than mapped to the SDK's `lake_query`. The plugin never asked the
  lake anything.
- **The suite's other v27 cases.** `an-exact-price` and
  `a-want-recorded-against`, about closes from ruling 537, stay presented:
  a NAV is recorded exactly and against the want. The rates cases are not
  presented (no reference rate, curve or index level);
  `records-a-datasets-liveness` is not presented, since Tiingo's NAVs are
  asked for once a day and never streamed, so there is no heartbeat; and
  `reports-its-feed-delay` is not presented, as ruling 518 says: core
  receives ReportLatency from contract v28.
- **Every page fits one screen** at 375, 582 and 1280 px, checked in a
  browser: Connection with no key leaves out Requests and Responses kept,
  nothing having been asked or kept, under the role's "No key yet".
  docs/troubleshooting.md is split under three headings, each a screen.
- **e2e**: the failure's logs under `.e2e/` are uploaded
  (`include-hidden-files`).
- **The pins**: open-meridian 0.32.2 and plugin-python:0.32.2 by tag; core
  v27's runtime and harness (a5da59a, merged as 6d346b3, chart 0.1.310) by
  tag and digest; `meridian` 0.1.52 in check.yaml.
- The README, AGENTS.md, docs/overview.md and the workflows' words about
  the pins and the delay brought up to date.

## 0.7.0

On open-meridian 0.31.0: pins only, no change to what the plugin records
or shows. It speaks contract v26, the SDK's, so the version is a minor one.

- **The pins**: open-meridian 0.31.0, as released on PyPI, and
  plugin-python:0.31.0 by tag in the Dockerfile; core v26's runtime and
  harness (17a13a2, merged as 648e25f, chart 0.1.308) by tag and digest;
  `meridian` 0.1.48 in check.yaml.
- **The data suite's v26 cases.** `queries-the-lake-within-bounds` is
  mapped in `tests/test_suite.py` as the SDK's data template maps it (one
  bounded query of prices, `lake_query`); the plugin itself asks the lake
  nothing. `hears-and-reads-an-event-group` is the SDK's; the outcome
  cases stay not presented.
- The README's, AGENTS.md's and the workflows' words about the pins
  brought up to date.

Earlier versions are described in the git history.
