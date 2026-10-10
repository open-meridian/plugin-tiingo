# Overview

A mutual fund does not trade on an exchange: you buy and sell it at the net
asset value per share it strikes once a business day, at the close in New
York. No exchange's data carries it, so a book holding a fund such as VIGIX
cannot be valued from closes alone. Tiingo publishes funds' NAVs, and its
free plan is enough for a few funds.

This plugin reads each fund you list from Tiingo and records its NAV for each
business day in your deployment's lake, where a reporting plugin values your
positions.

## What it records

- Each fund's NAV per share, for its date, in US dollars, exactly as Tiingo
  states it.
- Only mutual funds: a ticker Tiingo files as an ETF or a stock is shown on
  the Datasets tab and not recorded.

## When NAVs arrive

A fund strikes its NAV after the close; Tiingo has it after midnight New York
time. The plugin reads each fund's last days every six hours, so a NAV is
recorded by the next morning. Asked for an older day, it reads that day;
asked for a day with no NAV yet, it says the source has not stated it.

## What it does not do

- It shows no NAV on its own pages: NAVs are read by the plugins that value
  your book.
- It never asks for, shows or keeps your token anywhere but the deployment's
  secret settings.
