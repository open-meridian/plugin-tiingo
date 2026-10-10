"""`make e2e`: the plugin on the plugin harness of the runtime it pins
(contract v18), beside `reader`, a reporting plugin (e2e/reader.py) entitled
to its dataset, and the harness's admin. Run from the repository's root by
the Makefile, which builds the image and writes the harness's plugins first;
standard library only. No Tiingo token is ever set: the plugin's hosts file
sends Tiingo's API nowhere, and synthetic mode reads invented responses.

1. Waiting: with no token, Connection says it waits for the API token, and
   nothing is recorded.
2. Synthetic mode on, three funds listed: VIGIX, a mutual fund, resolved and
   its last days' NAVs recorded; VOO, an ETF, not served; NOSUCH, which
   Tiingo does not know.
3. Parity: through the deployment's MCP, `read_connection` and
   `read_datasets` answer what the pages show, the token said to be unset and
   never shown; and core's `dashboard__list_datasets` lists `tiingo:daily` as
   the catalogue declares it: push and pull, daily, New York's day ending at
   16:00, one person's terms.
4. Licensed (one person's terms) and the reader entitled.
5. Read back: VIGIX's NAV on 8 October 2026, 245.55 in dollars' cash
   instrument, kind nav, version 1.
6. Wanted: 22 September, not recorded, is asked of the plugin and recorded
   against the want; 12 October, which has no NAV yet, is declined
   `source_silent`.
7. Another source's record: VTSAX, listed in no Funds row and known to the
   deployment only as a custodian's book holds it (its CUSIP and the
   custodian's symbol), is wanted; the plugin reads the record (W3.6, a
   dgm's from contract v18 as ruled 2026-10-10), finds a mutual fund at
   Tiingo and records its NAV against the want: 147.4, keyed VTSAX's way;
   Datasets lists it, read from the record.
8. `store lake` is e2e/expected.lake, each subject named by its ticker.
9. A new container: it reads the funds again and records nothing twice.
"""

import json
import os
import subprocess
import sys
import time

PROJECT = "tiingo-e2e"
LOG = ".e2e/runner.log"
COMPONENTS = ".e2e/components.log"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", ".e2e/harness/compose.yaml",
           "-f", ".e2e/harness/plugins.yaml", "-f", "e2e/plugin.yaml"]
DATASET = "tiingo:daily"


class Failed(Exception):
    pass


def log(text):
    with open(LOG, "a", encoding="utf-8") as kept:
        kept.write(text + "\n")


def compose(*args, check=True, timeout=600):
    done = subprocess.run(COMPOSE + list(args), capture_output=True, text=True, timeout=timeout)
    log(f"$ compose {' '.join(args)[:300]}\n{done.stdout[-4000:]}{done.stderr[-2000:]}")
    if check and done.returncode != 0:
        raise Failed(f"compose {' '.join(args)[:200]}: {(done.stdout + done.stderr).strip()[-600:]}")
    return done


def runner(*args, check=True):
    done = compose("run", "--rm", "-T", "runner", *args, check=check)
    return done.stdout if check else done


def must(condition, why):
    if not condition:
        raise Failed(why)


def until(seconds, attempt, what):
    deadline = time.monotonic() + seconds
    last = None
    while True:
        try:
            answer = attempt()
        except Failed as failed:
            answer, last = None, failed
        if answer:
            return answer
        if time.monotonic() > deadline:
            raise Failed(f"{what}, in {seconds} seconds" + (f": {last}" if last else ""))
        time.sleep(2)


def page(instance, level, path):
    said = runner("page", "--instance", instance, "--level", level, path)
    status, _, body = said.partition("\n")
    must(status.strip() == "200", f"{instance} {path} answered {said[-600:]}")
    return body


def prices(subject, day):
    body = page("reader", "read", f"/prices?subject={subject}&date={day}&dataset={DATASET}&kind=nav")
    return json.loads(body)


def call(tool, arguments=None):
    done = runner("mcp", "call", tool, json.dumps(arguments or {}), check=False)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise Failed(f"{tool}: no answer: {(done.stdout + done.stderr)[-400:]}")
    must(answer.get("outcome") in ("read", "unchanged"), f"{tool} answered {done.stdout[-700:]}")
    return answer["data"]


def store_lake():
    return compose("run", "--rm", "-T", "store", "lake").stdout


def named(lines, names):
    out = []
    for line in lines.strip().splitlines():
        parts = line.split("|")
        if parts[0] == "row":
            parts[6] = names.get(parts[6], parts[6])
        elif parts[0] == "want":
            parts[3] = ",".join(names.get(s, s) for s in parts[3].split(","))
        out.append("|".join(parts))
    return "\n".join(sorted(out)) + "\n"


def run():
    started = time.time()
    compose("down", "-v", "--remove-orphans", check=False)
    compose("up", "-d")
    runner("ready")
    runner("ready", "--instance", "reader")

    # 1. Waiting for the token.
    runner("page", "--level", "admin", "/", "--until", "Waiting for the API token", "--seconds", "90")
    must("row|" not in store_lake(), "step 1, nothing recorded without a token")

    # 2. Synthetic mode, three funds.
    runner("settings", "synthetic=true", "funds[0].ticker=VIGIX", "funds[1].ticker=VOO",
           "funds[2].ticker=NOSUCH")
    runner("page", "--level", "admin", "/datasets", "--until", 'data-ticker="VIGIX" data-served="yes"',
           "--seconds", "120")
    until(60, lambda: store_lake().count("row|tiingo:daily|price|") >= 8,
          "step 2, VIGIX's last days were not recorded")

    # 3. Parity, and core's view of the catalogue.
    runner("grant", "--level", "admin")
    runner("mcp", "connect", "--covers", "deployment_admin", "--covers", "tiingo:admin")
    tools = runner("mcp", "list").split()
    read_connection = next((t for t in tools if t.endswith("read_connection")), "")
    read_datasets = next((t for t in tools if t.endswith("read_datasets")), "")
    must(read_connection and read_datasets, f"step 3, the plugin's two tools are listed: {tools}")
    connection = call(read_connection)
    must(connection["mode"] == "synthetic" and connection["token_set"] is False
         and connection["state"] == "ok", f"step 3, read_connection: {connection}")
    funds = {f["ticker"]: f for f in call(read_datasets)["funds"]}
    must(funds["VIGIX"]["served"] and funds["VIGIX"]["at_tiingo"] == "mutual fund"
         and funds["VIGIX"]["latest_recorded"] == "2026-10-09"
         and funds["VOO"]["at_tiingo"] == "not a mutual fund (NYSE)" and not funds["VOO"]["served"]
         and funds["NOSUCH"]["at_tiingo"] == "not found",
         f"step 3, read_datasets: {funds}")
    vigix = funds["VIGIX"]["instrument_id"]
    must(vigix in page("tiingo", "admin", "/datasets"), "step 3, Datasets shows what read_datasets answers")
    listed = {d["dataset"]: d for d in call("dashboard__list_datasets")["datasets"]}
    held = listed.get(DATASET, {})
    entry = held.get("catalogue_entry", {})
    must(entry.get("modes") == ["push", "pull"] and entry.get("day_time_zone") == "America/New_York"
         and entry.get("day_end_minute") == 960 and entry.get("cadence") == 86400
         and held.get("licence", {}).get("personal_use") is True,
         f"step 3, core lists the catalogue as declared: {held}")

    # 4. Licensed and entitled.
    runner("licence", DATASET, "kept=true", "retention_days=0", "derived_use=true", "display=true",
           "personal_use=true", "note=Tiingo's free plan: one person's use.")
    runner("entitle", "--instance", "reader", DATASET, "note=The e2e's reader reads the NAVs.")
    runner("grant", "--instance", "reader", "--level", "read", "--role", "reporting")

    # 5. Read back.
    read = until(60, lambda: (lambda r: r if r["prices"] else None)(prices(vigix, "2026-10-08")),
                 "step 5, VIGIX's NAV on 8 October was not read")
    nav = read["prices"]
    must(len(nav) == 1 and nav[0]["amount"] == "245.55" and nav[0]["kind"] == "PRICE_KIND_NAV"
         and nav[0]["version"] == 1 and nav[0]["instrument_id"] and nav[0]["instrument_id"] != vigix
         and nav[0]["row_key"] == "VIGIX:2026-10-08" and not nav[0]["published"],
         f"step 5, VIGIX's NAV in dollars' cash instrument: {nav}")

    # 6. Wants.
    asked = prices(vigix, "2026-09-22")
    must(asked["prices"] or any(u["reason"] == "UNANSWERED_REASON_ASKED_SOURCE" for u in asked["unanswered"]),
         f"step 6, 22 September is asked of the plugin: {asked}")
    past = until(90, lambda: (lambda r: r if r["prices"] else None)(prices(vigix, "2026-09-22")),
                 "step 6, 22 September was not recorded against the want")
    must(past["prices"][0]["amount"] == "245.34", f"step 6, 22 September's NAV: {past}")
    prices(vigix, "2026-10-12")
    until(90, lambda: "|declined|" in store_lake(), "step 6, 12 October was not declined")

    # 7. Another source's record, read and its NAV recorded.
    vtsax = json.loads(page("reader", "read", "/resolve"))["vtsax"]
    must(vtsax and vtsax != vigix, f"step 7, the custodian's VTSAX is its own record: {vtsax}")
    prices(vtsax, "2026-10-08")
    held = until(90, lambda: (lambda r: r if r["prices"] else None)(prices(vtsax, "2026-10-08")),
                 "step 7, VTSAX's NAV for the custodian's record was not recorded")["prices"]
    must(len(held) == 1 and held[0]["amount"] == "147.4" and held[0]["kind"] == "PRICE_KIND_NAV"
         and held[0]["row_key"] == "VTSAX:2026-10-08" and held[0]["subject"] == vtsax,
         f"step 7, VTSAX's NAV for another source's record: {held}")
    read = [f for f in call(read_datasets)["funds"] if f["ticker"] == "VTSAX"]
    must(len(read) == 1 and read[0]["served"] and read[0]["from_want"]
         and read[0]["instrument_id"] == vtsax, f"step 7, Datasets lists VTSAX, read: {read}")

    # 8. The lake.
    names = {vigix: "VIGIX", vtsax: "VTSAX"}
    got = named(store_lake(), names)
    with open(".e2e/lake", "w", encoding="utf-8") as kept:
        kept.write(got)
    with open("e2e/expected.lake", encoding="utf-8") as expected_file:
        expected = expected_file.read()
    if got != expected:
        diff = subprocess.run(["diff", "-u", "e2e/expected.lake", ".e2e/lake"], capture_output=True, text=True)
        raise Failed(f"step 8, the lake is not e2e/expected.lake:\n{diff.stdout[-3000:]}")

    # 9. A new container records nothing twice.
    compose("up", "-d", "--no-deps", "--force-recreate", "tiingo")
    runner("ready")
    until(120, lambda: "VIGIX: 0 NAVs recorded, 0 restated, 8 unchanged"
          in compose("logs", "--no-color", "tiingo").stdout,
          "step 9, the new container's check was not answered unchanged")
    again = named(store_lake(), names)
    must(again == got, "step 9, the new container recorded something twice")

    rows = got.count("row|")
    print(f"e2e OK in {int(time.time() - started)}s on the plugin harness, no Tiingo token: waiting "
          f"said with none, nothing recorded; synthetic mode with VIGIX, VOO and NOSUCH listed, VIGIX "
          f"alone served (VOO an ETF, NOSUCH not found); read_connection and read_datasets answering "
          f"what the pages show, the token said unset and never shown; core listing {DATASET} as "
          f"declared, one person's terms; licensed and entitled; VIGIX's NAV on 8 October read back "
          f"at 245.55 in dollars, kind nav; 22 September wanted and recorded, 12 October declined "
          f"source silent; VTSAX, known only by a custodian's CUSIP and symbol, read from its "
          f"record and its NAV recorded against the want (147.4); `store lake` as e2e/expected.lake ({rows} rows); and a new container "
          f"recording nothing twice")


def main():
    os.makedirs(".e2e", exist_ok=True)
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError, TypeError) as failed:
        with open(COMPONENTS, "a", encoding="utf-8") as kept:
            kept.write(compose("logs", "--no-color", check=False).stdout)
        compose("down", "-v", "--remove-orphans", check=False)
        print(f"e2e FAILED: {failed}; the runner's log is in {LOG}, the components' in {COMPONENTS}",
              file=sys.stderr)
        return 1
    compose("down", "-v", "--remove-orphans", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
