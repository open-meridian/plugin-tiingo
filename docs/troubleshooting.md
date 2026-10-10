# Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| **Waiting for the API token** | No token is set | Enter yours in Settings, under API token |
| **Tiingo refused the token** | Tiingo answered 401 or 403 | Check the token on your Tiingo account's API page, and enter it again |
| **Tiingo's limit was reached** | Too many requests for the plan, here or elsewhere with the same token | Nothing: the plugin waits and tries again |
| A fund **not a mutual fund** | Tiingo files the ticker as an ETF or a stock | Its closes come from an equity dataset; remove it from Funds |
| A fund **not found** | Tiingo knows no such ticker | Check the ticker |
| A fund **ambiguous** or **not found** as an instrument | Its ticker found two records, or none to use | Pick its record in the Funds row's Instrument column |
| A day declined, *source silent* | Tiingo has no NAV for it yet | Wait for the night after the business day |
