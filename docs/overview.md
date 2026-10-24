# Overview

A mutual fund does not trade on an exchange: you buy and sell it at the net
asset value per share it strikes once a business day, at the close in New
York. No exchange's data carries it, so a book holding a fund such as VIGIX
cannot be valued from closes alone. Tiingo publishes funds' NAVs, and its
free plan is enough for a few funds.

It is a data plugin: its first-use path, its two pages and its Summary figures are every data plugin's, described once on [Using a data plugin](https://open-meridian.dev/how-to/using-a-data-plugin/). These sections cover what is Tiingo's own.

This plugin reads each fund you list from Tiingo and records its NAV for each
business day in your deployment's lake, where a reporting plugin values your
positions.

## What it records

- Each fund's NAV per share, for its date, in US dollars, exactly as Tiingo
  states it.
- Only mutual funds: a ticker Tiingo files as an ETF or a stock is shown on
  the Datasets tab and not recorded.

## How a fund meets its record

Tiingo names a fund by its ticker alone, and a ticker is no open identifier.
So each ticker is first mapped through OpenFIGI to the fund's FIGIs, which
the plugin states beside Tiingo's symbol when it resolves the fund, so the
fund meets the platform's record for it and the NAV values the position you
hold. Where OpenFIGI finds no instrument, or more than one, nothing is
guessed: the fund is resolved by Tiingo's symbol alone.

## When NAVs arrive

A fund strikes its NAV after the close; Tiingo has it after midnight New York
time. The plugin reads each fund's last days every six hours, so a NAV is
recorded by the next morning. The dataset declares that delay, eight hours
from 16:00 to midnight New York time, so a NAV is not judged late while
Tiingo cannot have it yet. Asked for an older day, it reads that day;
asked for a day with no NAV yet, it says the source has not stated it.

## What it does not do

- It shows no NAV on its own pages: NAVs are read by the plugins that value
  your book.
- It never asks for, shows or keeps your token anywhere but the deployment's
  secret settings.
