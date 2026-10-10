# Pages

Both pages are under **Manage**, for the plugin's admins. Neither shows a NAV
or your token. Each is also a read tool on the deployment's MCP, answering
what the page shows.

## Connection (`read_connection`)

How the plugin reaches Tiingo: live, synthetic, or waiting for its token; the
token set or not (never shown); the requests made this hour and today against
the free plan's limits it keeps; the last check and why it failed if it did;
and how many responses are kept.

## Datasets (`read_datasets`)

What the plugin serves: its one dataset as the deployment's catalogue lists
it, with the licence it declares; the standing wants it keeps current and the
last wants it answered; and each fund listed, one line each: what Tiingo says
it is, the deployment's record for it or why there is none, and the latest
day recorded. A row's `…` opens its details.
