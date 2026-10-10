# Setup

## Your token

You need your own Tiingo account; its free plan suffices for a few funds.
In the dashboard, open this plugin's **Settings** and enter the token from
your Tiingo account's API page in **API token**. It is a secret setting:
nobody sees it again, and the plugin sends it only to Tiingo.

Until it is set, the plugin waits and reads nothing.

## Your funds

Under **Funds**, add a row for each mutual fund to keep NAVs for: its ticker,
such as `VIGIX`. Where your custodian's positions already name the fund's
record in this deployment, pick it in the row's **Instrument** column, so the
NAV values the position you hold; otherwise the plugin finds or makes the
record by Tiingo's symbol.

A fund your custodian's positions name needs no row at all for a reader to
value it: when the reader asks for its NAV, the plugin reads the record, and
where the record carries a ticker Tiingo files as a mutual fund, it records
the NAV and keeps the fund current from then on. Datasets lists such a fund
as read from its record. Funds and these count together toward the plugin's
100.

## Its dataset

On the deployment's **Data sources** page (deployment admins):

1. **License `<instance>:daily`.** The catalogue's default is one person's
   terms, as Tiingo's free plan is. Confirm it, or set your own, with a note.
2. **Entitle** your reporting plugin to it.
3. **Priority** for NAVs, where another dataset also gives them.

## Try it without a token

On a deployment installed for development, **Synthetic mode** serves
invented responses for VIGIX and VOO, with no token.
