# Pages

Both pages are the data role's, the same on every data plugin, under
**Manage**, for the plugin's admins. Neither shows a NAV or your token. Each
is also a read tool on the deployment's MCP, answering what the page shows,
under the same names on every data plugin.

## Connection (`read_connection`)

**Key:** the mode (Live, Sample data or No key), the API token set or not
(never shown), what Tiingo serves the token, and where it reads. **Limits
and use:** the free plan's limits it keeps, its requests since it started,
this hour and today, the last check and why it failed if it did, and how
many responses are kept. **Stream:** it does not stream. With no token, "No
key yet", linking to Settings.

## Datasets (`read_datasets`)

**Served:** its one dataset as the deployment's catalogue lists it, with the
terms it declares and whether a deployment admin has licensed it, and what
it recorded and declined. **Wants:** the standing wants it keeps current and
the last wants it answered. **Subjects:** whether it may read an
instrument's record. Then **Funds**: each fund listed, or read from the record a
reader's want named, one line each: what Tiingo says it is, the deployment's
record for it or why there is none, and the latest day recorded. A row's `…` opens its details,
among them the FIGI OpenFIGI mapped its ticker to, or that none was found.
