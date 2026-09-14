#!/usr/bin/env python3
"""
Verification suite for the EcoSip multi-stage AI workflow.

Run from the repository root:

    python3 tests/verify.py

No third-party packages are required - only the Python standard library, so a
reviewer can clone the repo and run this immediately.

Four groups of checks, one per claim the write-up makes:

  A. CONTRACT   - the Stage 1 -> Stage 2 handoff (the shape of data.json).
  B. WIRING     - the Stage 2 artefacts really consume that contract.
  C. PACKAGING  - the Stage 3 artefact really packages what the app needs.
  D. SMOKE      - the site actually serves and the fetch path actually works,
                  against a live HTTP server on an ephemeral port.

Exit code is 0 when every check passes, 1 otherwise.
"""

import functools
import http.server
import json
import pathlib
import re
import socketserver
import sys
import threading
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent

PASSED = 0
FAILED = []


def check(group, name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
        print("  PASS  [{}] {}".format(group, name))
    else:
        FAILED.append((group, name, detail))
        print("  FAIL  [{}] {}{}".format(group, name, " -- " + detail if detail else ""))


def read(name):
    path = ROOT / name
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------- A. CONTRACT
# Stage 1 (Chat UX) promised: a raw JSON array of objects with exactly
# 'question' and 'answer' keys. Everything downstream depends on that promise,
# so it is checked first and checked strictly.

print("\nA. CONTRACT  - Stage 1 -> Stage 2 handoff (data.json)")

raw = read("data.json")
check("A", "data.json exists", raw is not None)

faqs = None
if raw is not None:
    try:
        faqs = json.loads(raw)
        check("A", "data.json is valid JSON", True)
    except json.JSONDecodeError as exc:
        check("A", "data.json is valid JSON", False, str(exc))

if faqs is not None:
    check("A", "top level is an array", isinstance(faqs, list),
          "got {}".format(type(faqs).__name__))

if isinstance(faqs, list):
    check("A", "contains exactly 5 entries", len(faqs) == 5,
          "got {}".format(len(faqs)))

    bad_shape = [i for i, item in enumerate(faqs)
                 if not isinstance(item, dict) or set(item) != {"question", "answer"}]
    check("A", "every entry has exactly the keys question/answer", not bad_shape,
          "offending indexes: {}".format(bad_shape))

    bad_values = [i for i, item in enumerate(faqs)
                  if not isinstance(item, dict)
                  or not all(isinstance(item.get(k), str) and item.get(k, "").strip()
                             for k in ("question", "answer"))]
    check("A", "every question and answer is a non-empty string", not bad_values,
          "offending indexes: {}".format(bad_values))

    questions = [item.get("question") for item in faqs if isinstance(item, dict)]
    check("A", "no duplicate questions", len(questions) == len(set(questions)))
    check("A", "every question is phrased as a question",
          all(isinstance(q, str) and q.rstrip().endswith("?") for q in questions))


# ------------------------------------------------------------------ B. WIRING
# Stage 2 (IDE UX) produced index.html + styles.css + script.js. These checks
# assert the generated front end really consumes the contract above, including
# the accessibility attributes the IDE agent added on its own.

print("\nB. WIRING    - Stage 2 artefacts consume the contract")

html = read("index.html")
js = read("script.js")
css = read("styles.css")

check("B", "index.html exists", html is not None)
check("B", "script.js exists", js is not None)
check("B", "styles.css exists", css is not None)

if html:
    check("B", "index.html links styles.css", 'href="styles.css"' in html)
    check("B", "index.html loads script.js", 'src="script.js"' in html)
    check("B", "index.html has the #faq-container mount point",
          'id="faq-container"' in html)
    check("B", "index.html ships no inline <style> block",
          "<style" not in html.lower(),
          "styling lives in styles.css - see the deviation note in README.md")

if js:
    check("B", "script.js fetches data.json", "fetch('data.json')" in js or 'fetch("data.json")' in js)
    check("B", "script.js handles a failed fetch", ".catch(" in js)
    check("B", "script.js sets aria-expanded", "aria-expanded" in js)
    check("B", "script.js sets aria-controls", "aria-controls" in js)
    check("B", "script.js sets aria-hidden", "aria-hidden" in js)
    check("B", "script.js generates per-item unique ids",
          "faq-button-${index}" in js and "faq-content-${index}" in js)
    check("B", "script.js closes other open items (accordion behaviour)",
          ".faq-item.active" in js)

if css:
    check("B", "styles.css styles the open state", ".faq-item.active" in css)
    check("B", "styles.css animates the answer panel",
          re.search(r"\.faq-answer-wrapper\s*\{[^}]*max-height", css, re.S) is not None)


# --------------------------------------------------------------- C. PACKAGING
# Stage 3 (CLI UX) produced deploy.ps1. The original notes claimed a deploy.sh;
# see "Deviations from the prompts" in README.md. This check pins the real file
# and makes sure it packages all four runtime artefacts, not just two.

print("\nC. PACKAGING - Stage 3 artefact (deploy.ps1)")

ps1 = read("deploy.ps1")
check("C", "deploy.ps1 exists", ps1 is not None)
if ps1:
    for artefact in ("index.html", "styles.css", "script.js", "data.json"):
        check("C", "deploy.ps1 packages {}".format(artefact), artefact in ps1)
    check("C", "deploy.ps1 names an output archive", "ecosip_deploy.zip" in ps1)


# -------------------------------------------------------------------- D. SMOKE
# The page cannot be opened from the file system - fetch() needs a real origin.
# This starts the same kind of static server Stage 3 used, on an ephemeral port,
# and proves the site serves and the JSON survives the round trip.

print("\nD. SMOKE     - live HTTP server round trip")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


handler = functools.partial(QuietHandler, directory=str(ROOT))
httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
port = httpd.server_address[1]
thread = threading.Thread(target=httpd.serve_forever, daemon=True)
thread.start()
base = "http://127.0.0.1:{}".format(port)
print("  (serving the repository root on {})".format(base))

try:
    def get(path):
        with urllib.request.urlopen(base + path, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")

    for path, needle in (("/index.html", "EcoSip FAQs"),
                         ("/script.js", "faq-container"),
                         ("/styles.css", ".faq-item")):
        try:
            status, body = get(path)
            check("D", "GET {} returns 200".format(path), status == 200, "got {}".format(status))
            check("D", "GET {} returns real content".format(path), needle in body,
                  "expected to find {!r}".format(needle))
        except urllib.error.URLError as exc:
            check("D", "GET {} succeeds".format(path), False, str(exc))

    try:
        status, body = get("/data.json")
        check("D", "GET /data.json returns 200", status == 200, "got {}".format(status))
        check("D", "served data.json is identical to the committed file",
              json.loads(body) == faqs)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        check("D", "GET /data.json succeeds", False, str(exc))

    try:
        get("/does-not-exist.json")
        check("D", "a missing file returns 404 (the .catch path is reachable)", False,
              "server returned success for a missing file")
    except urllib.error.HTTPError as exc:
        check("D", "a missing file returns 404 (the .catch path is reachable)",
              exc.code == 404, "got {}".format(exc.code))
finally:
    httpd.shutdown()
    httpd.server_close()


# ------------------------------------------------------------------- SUMMARY

total = PASSED + len(FAILED)
print("\n" + "-" * 62)
print("{} checks run: {} passed, {} failed".format(total, PASSED, len(FAILED)))
if FAILED:
    print("\nFailures:")
    for group, name, detail in FAILED:
        print("  [{}] {}{}".format(group, name, " -- " + detail if detail else ""))
print("-" * 62)

sys.exit(1 if FAILED else 0)
