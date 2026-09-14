# Verification Log

This file records an actual run of the verification suite, not a description of one. The output in section 3 is pasted from stdout without editing.

See [`README.md`](README.md) for the workflow record this verifies.

---

## 1. Environment

```
Python:   3.10.12
Platform: Linux-6.8.0-136-generic-x86_64-with-glibc2.35
Date:     2026-09-14 08:13 UTC
Commit:   f79b401 (working tree, pre-commit)
```

The suite uses only the Python standard library, so it runs anywhere Python 3.8+ is installed. It was run from the repository root:

```bash
python3 tests/verify.py
```

## 2. What is checked, and why

| Group | Checks | The claim it defends |
|---|---|---|
| **A. Contract** | 8 | The Stage 1 output really is a flat array of `{question, answer}` objects with non-empty string values. This is the only thing the rest of the chain depends on, so it is checked strictly. |
| **B. Wiring** | 16 | The Stage 2 artefacts really consume that contract: `index.html` mounts `#faq-container` and links the other two files, `script.js` fetches `data.json`, handles a failed fetch, and sets the `aria-*` attributes and unique ids the IDE agent added, `styles.css` defines the open state and the animated panel. |
| **C. Packaging** | 6 | `deploy.ps1` exists and packages all four runtime files, not the two the original prompt asked for. This is the regression that would silently ship a broken archive. |
| **D. Smoke** | 9 | The site actually serves. A `http.server` is started on an ephemeral port over the real repository, each file is fetched over HTTP, the served `data.json` is compared to the committed one, and a missing file is confirmed to return 404 so the `.catch` branch in `script.js` is reachable. |

## 3. Run output

```text

A. CONTRACT  - Stage 1 -> Stage 2 handoff (data.json)
  PASS  [A] data.json exists
  PASS  [A] data.json is valid JSON
  PASS  [A] top level is an array
  PASS  [A] contains exactly 5 entries
  PASS  [A] every entry has exactly the keys question/answer
  PASS  [A] every question and answer is a non-empty string
  PASS  [A] no duplicate questions
  PASS  [A] every question is phrased as a question

B. WIRING    - Stage 2 artefacts consume the contract
  PASS  [B] index.html exists
  PASS  [B] script.js exists
  PASS  [B] styles.css exists
  PASS  [B] index.html links styles.css
  PASS  [B] index.html loads script.js
  PASS  [B] index.html has the #faq-container mount point
  PASS  [B] index.html ships no inline <style> block
  PASS  [B] script.js fetches data.json
  PASS  [B] script.js handles a failed fetch
  PASS  [B] script.js sets aria-expanded
  PASS  [B] script.js sets aria-controls
  PASS  [B] script.js sets aria-hidden
  PASS  [B] script.js generates per-item unique ids
  PASS  [B] script.js closes other open items (accordion behaviour)
  PASS  [B] styles.css styles the open state
  PASS  [B] styles.css animates the answer panel

C. PACKAGING - Stage 3 artefact (deploy.ps1)
  PASS  [C] deploy.ps1 exists
  PASS  [C] deploy.ps1 packages index.html
  PASS  [C] deploy.ps1 packages styles.css
  PASS  [C] deploy.ps1 packages script.js
  PASS  [C] deploy.ps1 packages data.json
  PASS  [C] deploy.ps1 names an output archive

D. SMOKE     - live HTTP server round trip
  (serving the repository root on http://127.0.0.1:37059)
  PASS  [D] GET /index.html returns 200
  PASS  [D] GET /index.html returns real content
  PASS  [D] GET /script.js returns 200
  PASS  [D] GET /script.js returns real content
  PASS  [D] GET /styles.css returns 200
  PASS  [D] GET /styles.css returns real content
  PASS  [D] GET /data.json returns 200
  PASS  [D] served data.json is identical to the committed file
  PASS  [D] a missing file returns 404 (the .catch path is reachable)

--------------------------------------------------------------
39 checks run: 39 passed, 0 failed
--------------------------------------------------------------
```

**Result: 39 checks run, 39 passed, 0 failed. Exit code 0.**

## 4. Negative control

A test suite that has never failed has not been shown to work. Before recording the run above, the suite was run against a deliberately corrupted copy of `data.json` (one key renamed from `answer` to `answr`, and a sixth entry appended) in a scratch directory, leaving the real repository untouched.

It reported:

```text
39 checks run: 36 passed, 3 failed

Failures:
  [A] contains exactly 5 entries -- got 6
  [A] every entry has exactly the keys question/answer -- offending indexes: [2]
  [A] every question and answer is a non-empty string -- offending indexes: [2]
```

Exit code 1. The three failures are exactly the three broken properties, with the offending index named. The contract check does what it claims to do.

## 5. Manual checks not covered by the suite

These were verified by hand in Brave against `http://localhost:8080` and are evidenced by [`docs/stage3-served-result.png`](docs/stage3-served-result.png). They are listed here because the automated suite does **not** cover them.

| Check | Result |
|---|---|
| All five questions render on load | Pass |
| Clicking a question expands its answer with the height animation | Pass |
| Opening one panel closes any other open panel | Pass |
| The `+` icon rotates to `x` on the open item | Pass |
| Layout holds at narrow widths (the `max-width: 600px` rules) | Pass |
| Opening `index.html` directly from the file system fails with the "start a local web server" message | Pass, and this is the intended behaviour - it is why Stage 3 exists |

Two further checks were run on 14 September 2026 and captured:

| Check | Result | Evidence |
|---|---|---|
| Static server serves the whole chain: `/`, `styles.css`, `script.js` and `data.json` all return 200 | Pass | [`docs/stage3-cli-rerun.png`](docs/stage3-cli-rerun.png) |
| `deploy.ps1` runs and reports success under PowerShell, and fails under bash as expected for a Windows-only script | Pass | [`docs/stage3-deploy-rerun.png`](docs/stage3-deploy-rerun.png) |
| `ecosip_deploy.zip` extracts to exactly the four runtime files, with byte counts matching the committed originals (`data.json` 1457, `index.html` 1091, `script.js` 3049, `styles.css` 3879) | Pass | `Expand-Archive` run by hand in PowerShell |

## 6. What is still not verified

- **No automated browser or DOM test.** Group D proves the files serve and the JSON survives the round trip. It does not click anything. Every interaction row in section 5 rests on a human looking at the screen, not on a test. Adding Playwright would close this gap and would also make a demo recording reproducible.
- **No demo video.** The screenshots in `docs/` show the start, middle and end states, not the accordion in motion.
- **The Stage 3 terminal captures are re-runs.** They were recorded on 14 September 2026, not during the original July run, and are labelled as such in the README. They show the stage reproduces; they are not a record of the night itself.
- **`deploy.ps1` is not exercised by the automated suite.** Group C reads the script and asserts it names all four runtime files; it does not run `Compress-Archive`, because the suite is written to run on any platform. The script itself was run by hand and its archive extracted and checked (see section 5), so the gap is that this check is manual and would not catch a future regression, not that it is unverified.
- **The FAQ content is not fact-checked.** EcoSip is fictional and its claims were generated by a language model. The suite checks the shape of the content, never its truth.
