# Changelog

## 0.9.0

On open-meridian 0.35.1, contract v29 (rulings 1003, 1004, 1005, 1009 to
1029, 602), on core v29's harness; from 0.32.2, past contract v28. What the
plugin records is unchanged.

- **One class for its role** (open-meridian 0.35: each role is one class).
  `Feed` is a `meridian.roles.data.Role`, its acts made on itself; `Lake`
  extends it and is registered with `meridian.run`, which applies the first
  settings (`Lake.on_settings`: the token, sample data and the funds, the
  responses' window tended) before anything is heard and watches them again
  should their stream break, serves the pages, sets the figures on each
  heartbeat, hands what the lake wants to the class and starts `Lake.run` --
  the funds read every six hours or when the settings change, storage
  tended daily, the licences read every minute -- again after a backoff
  should it fail. The tasks it wired by hand are gone.
- **The settings declared untyped for now**: open-meridian 0.35.1's
  `meridian.run` delivers a typed settings class without the SDK's own
  settings, the responses' window among them, which tending reads; the
  declaration names `Declared.declared()` until 0.35.2.
- **The suite's v28 and v29 cases** (ruling 602): its feed delay is about
  publication times, which Tiingo never states of a NAV (its dataset
  declares the delay); option chains, filings, holdings, corporate actions,
  ratings, derived series and pools' factors are not presented, a fund's
  NAV being none of them.
- **`meridian plugin migrate --to 0.35.1`** moved the pins and rewrote
  `ops.SubjectRef` to `meridian.SubjectRef`, the feed's construction and
  handlers (the connection no longer given to it; `on_want` and
  `on_withdrawn` as `on_observations_wanted` and `on_want_withdrawn`) and
  its acts (`self.plugin.<act>` as `self.<act>`). The entry point, the
  tests' recorder (`Recorder.bind`, `Recorder.hear`), the suite's cases and
  the e2e's reader (two role classes -- `custody`, `reporting` -- on
  `meridian.run_async`) were moved by hand.
- **The pins:** open-meridian 0.35.1 and plugin-python:0.35.1 by tag and
  digest (`sha256:cdc92bc9...71a9b614`); core's runtime and harness
  `1ae36f0` (merged as 3f99222, chart 0.1.339) by digest; meridian 0.1.56
  in check.yaml.

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
