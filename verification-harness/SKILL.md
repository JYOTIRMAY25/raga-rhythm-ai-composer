---
name: verification-harness
description: Evidence-gated workflow for any task that writes, fixes, or refactors code. Pins acceptance criteria before coding, attacks the result with adversarial tests designed from the spec (never from the implementation), dry-runs every critical path, executes the project's real test/lint/typecheck/build commands, and repairs in a bounded loop that never weakens a test. Use it for ANY code change — features, bug fixes, refactors, scripts, PRs — even when the user doesn't explicitly ask for verification, and always when they say verify, test it, prove it works, harden, no regressions, or ship it. Nothing is "done" without fresh passing output.
license: MIT
---

# Verification Harness

Follow the stages in order for any task that writes or changes code. Every rule carries a
one-line why — when a case isn't covered, follow the why. Self-contained: no scripts, no
installs; use whatever shell and test tools are already available.

## The 6 rules (never break)

1. **No evidence = not done.** Never say "done / fixed / works / passes" without running the
   checks AFTER your last edit and pasting their real output. Only exit codes and output count.
2. **Never weaken a test.** No deleting, skipping, `xfail`/`.only`, commenting out, loosening
   an assertion, or changing an expected value to make a test pass. No special-casing test
   inputs, no mocking the code under test, no suppressions (`# type: ignore`, `@ts-ignore`,
   `eslint-disable`, `# noqa`, empty `catch`/`except: pass`). Sole exception: a test that
   contradicts a written AC — see TEST FIX in Stage 5. *Why: a bent test goes green while the
   bug ships.*
3. **Evidence must be fresh.** Any edit after a run invalidates that run — run again.
4. **Adversarial tests come from the spec, never from the implementation.** Tests designed by
   the mind that wrote the code share its blind spots. Expected values cite an AC — never
   derive one by running the code.
5. **Smallest real change.** No placeholder comments that delete code (`// ... existing
   code ...`); never call an API, function, or package you haven't confirmed exists (open the
   file or docs first); no new dependency without the user's OK.
6. **An honest NOT VERIFIED beats a fake PASS.** Out of repair budget, or the spec is
   ambiguous → report NOT VERIFIED with reasons and stop.

Keep a running LEDGER (template at the end) in your working notes or scratch space — never
committed into the user's repo.

## Stage 0 — Spec and attack plan (before touching code)

1. Write the **task** in one line.
2. Write **acceptance criteria** as observable behavior — input → output / error / side
   effect — including what must NOT change. Number them `AC1, AC2, …`.
3. List **critical paths**, each linked to ACs. Minimum: one `happy` AND one `error` or
   `boundary` path. Add `state`, `security`, `concurrency` paths when the change touches
   writes/caches, untrusted input, or shared state. Every AC gets ≥1 path.
4. **Write the adversarial case list NOW**, from spec + interface only (catalog in Stage 2).
   *Why: designing the attacks before the implementation exists is what makes them independent
   when you have no subagent — you can't design around code you haven't written.*
5. Find the project's **real commands**, in this order: `package.json` scripts /
   `Makefile`/`justfile` → CI config (`.github/workflows/*`) → README/CONTRIBUTING → the
   stack's standard defaults. Record test, lint, typecheck, build in the ledger.
6. **Run the test command once NOW.** Record what already fails. *Why: pre-existing failures
   aren't yours to fix (unless asked) and must not be blamed on your change.*

Scaling: trivial change (≤ ~20 lines, no branching logic) → 1 path, 3 adversarial cases.
Auth, payments, data loss, security, concurrency → double every minimum.

## Stage 1 — Implement

1. Smallest change that satisfies the ACs; leave unrelated code alone. *Why: broad rewrites
   create untested regressions.*
2. Confirm every function, flag, or package exists with that exact signature before using it.
3. Do NOT edit existing tests. Adding new test files is fine.

## Stage 2 — Adversarial tests (try to BREAK it)

Turn the Stage-0 attack plan into runnable tests. Output is **tests, never opinions**.

Executor — most independent option available:
- **Subagent / fresh session** (best): give it ONLY the task line, ACs, critical paths, public
  interface, and test command. Not your reasoning, not the function bodies.
- **Yourself** (no subagent): implement the Stage-0 case list as written. Do not re-derive
  cases by reading the implementation — that's how tests inherit its blind spots.

Requirements:
1. NEW test files only (e.g. `test_adv_<feature>.*`). Never edit existing tests; never fix
   code from inside this role.
2. Cover every critical path: **≥5 cases across ≥3 catalog categories**.
3. **≥1 property/fuzz test**: many generated inputs checked against an invariant or a
   brute-force oracle (`parse(format(v)) == v`; result matches a slow obviously-correct
   version). *Why: catches special-casing and off-by-ones that example tests miss.* If
   genuinely no invariant applies (pure wiring/glue), log a one-line exemption in the ledger
   instead of writing a fake one.
4. Every expected value cites its AC.

**Attack catalog** (pick what applies):
- **boundary:** 0, 1, −1, max, max+1, first/last element, exactly-at-limit, off-by-one ranges
- **input:** empty string/list/dict, `None`/`null`/`undefined`, whitespace-only, huge input,
  unicode, NaN/Infinity, very long strings
- **error:** wrong types, missing fields, malformed data, dependency failure, timeouts —
  assert the RIGHT error, not just "an error"
- **state:** repeated calls, idempotency, order of operations, stale cache, partial failure
  leaving half-written state, rollback
- **concurrency:** two calls at once, double submit, race on shared state
- **security:** injection (SQL/shell/path `../`), unescaped HTML, auth bypass, secrets in
  logs, unbounded resource use
- **api-misuse:** wrong call order, use-after-close, unknown params
- **regression:** behavior the ACs say must not change
- **language traps:** Python — mutable default args, `is` vs `==`, float equality. JS/TS —
  `==` coercion, falsy `0`/`""`, un-awaited async, Date/timezone. Go — nil maps, ignored
  errors, loop-var capture. SQL — NULL semantics, empty `IN`. Everywhere — timezones,
  encoding, pagination off-by-one, integer overflow.

Register each case in the ledger: `id | path | category | expected (ACn)`.

## Stage 3 — Dry-run every critical path (trace, don't guess)

Before executing anything, walk the code **as written, line by line** (not as you meant it)
for **≥2 concrete inputs per path** — one normal, one edge:

| input | branches (line: condition → result) | key state | actual | expected (ACn) | ✓/✗ |
|---|---|---|---|---|---|

Trace loops at iteration 1, 2, last, and exit. Write down the return value you assumed for
every external call. Any ✗ → Stage 5. *Why: the trace forces a prediction before the run —
a wrong prediction means you don't understand the code yet — and it is the ONLY evidence when
nothing can execute.*

## Stage 4 — Execute everything

1. Run: full test suite + adversarial tests + lint + typecheck + build (whichever exist).
   Use a timeout; never watch mode.
2. Read the actual output; when describing a failure, quote the real lines. Never summarize
   output you did not see.
3. These count as **FAIL**: nonzero exit · "0 tests ran" / none collected · all skipped ·
   timeout · collection crash. *Why: a filter matching nothing exits 0 and looks green.*
4. No test framework in the project ≠ skip execution: write a minimal test with the standard
   library (`unittest`, `node:test`, `go test`, …) and run it.
5. Ledger: command → exit code → pass/fail counts → key lines.

## Stage 5 — Repair loop (max 5 iterations)

Take the FIRST failure; for each iteration:
1. **Reproduce:** read the full output.
2. **Root cause:** exact line + why it's wrong. Fix the cause, not the symptom.
3. **Who is wrong?** The CODE, by default. Only if the test contradicts a specific AC: quote
   the AC, fix the test to match it, log `TEST FIX: <AC + reason>`. Spec ambiguous → stop and
   ask; don't guess.
4. **Minimal fix.** Log `R<n> | failure | root cause (line + why) | fix`.
5. **Re-run EVERYTHING** (Stage 4), not just the failing test. *Why: fixes break other
   things; the full re-run is the regression guard.* Re-trace (Stage 3) any path whose code
   changed.

Stop conditions: all green → Stage 6 · same failure after 2 attempts → discard your theory,
re-read spec + failure from zero (fresh subagent if available) · 5 iterations, oscillation
(fixing A breaks B breaks A), or test-vs-spec conflict → STOP, report NOT VERIFIED.

**Forbidden fixes** (each one ships the bug with a green light):
delete / skip / comment out a test · change an expected value to match output ·
`if input == <test value>` special-casing · mock the function under test · add suppressions
or empty catch blocks · narrow the test command or run fewer tests · placeholder comments
replacing real code.

## Stage 6 — The gate

Declare **PASS** only if every box is honestly true:

- [ ] Every AC covered by ≥1 path; every path has ≥1 adversarial case and an all-✓ trace
      redone after the last edit.
- [ ] ≥5 adversarial cases across ≥3 categories; property test present (or logged exemption).
- [ ] Suite + adversarial tests + lint/typecheck/build ran AFTER the last edit, exit 0, and
      ran >0 tests.
- [ ] No test weakened (except a logged TEST FIX backed by a quoted AC); no new suppressions,
      special-cases, or mocks of the code under test.
- [ ] Every repair iteration has a root cause logged; budget not exceeded.

Any box false → back to Stage 5, or report NOT VERIFIED. Never soften it to "mostly works".

**Final message format (always):**

```text
VERIFICATION: PASS | NOT VERIFIED
Checks (run after last edit):  <command> → exit <n> · <X passed / Y failed>   (one line each)
Adversarial: N cases / K categories (bugs found: B) · Traces: P paths ✓ · Repairs: R
Evidence: <key output lines of the final runs>
Limits: <anything not executed, disabled, or environment-limited>
```

## If you cannot execute commands

Do Stages 0–3 fully in writing — ACs, paths, adversarial tests as real test code, and a trace
table for EVERY path (mandatory: it is your only evidence). The verdict is always
`NOT VERIFIED — tests not executed`; give the user the exact commands to run. When they paste
output produced AFTER your final edit, apply the Stage-6 gate to it.

## Ledger template

```markdown
# Ledger — <task, one line>
ACs: AC1 … · AC2 …
Paths: P1 [happy] … (AC1) · P2 [error] … (AC2)
Commands: test … · lint … · typecheck … · build …   Baseline failures: …
Adversarial: | id | path | category | expected (AC) | result |
Traces:      | path | input | branches | actual | expected | ✓/✗ |
Runs:        | command | exit | counts | key lines |
Repairs:     | R# | failure | root cause (line + why) | fix |
Verdict: PASS | NOT VERIFIED — <reasons>
```
