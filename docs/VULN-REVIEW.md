# Vulnerability review — participant-side audit (2026-08-11)

Method: four parallel sub-agent audits scoped by `docs/THREAT-MODEL.md`
(parser/TB4, geometry C4+C6, scoring C5, DoS/channel A4+C2). Attacker model:
**participant only** — controls the bytes of `submission/best.heesch` and,
conditionally, the file *types* under `submission/` (git tracks symlinks; the
workflow surface check inspects path names only). Admin/operator/platform
compromise out of scope. **Every finding below was executed against the real
harness** (`python3 -m harness.verify`, `PYTHONHASHSEED=0`, scratch repo); no
repo files were modified.

Remediation status is tracked in `docs/REVIEW-FIXES.md`; the `fix/audit-2026-08`
branch implements V1–V12 and the record-tier launch blockers F1–F5.

## Executive summary

The mathematical core held completely: **no way exists to get an invalid
witness accepted, inflate hc/hh, overstate defect credit, or make `score.json`
exceed what the geometry justifies.** The fail-closed invariant (rejection ⇒
nonzero exit ⇒ no score file) held in every one of ~200 directed cases and
~10 000 fuzz cases across the four audits.

The exploitable surface is exactly where the threat model pointed, with one
assessment correction: **the tiler-gate coverage gap (R3) is trivially
exploitable, not exotic** — a 20-line construction scores 5.0, above the
class record of 4, with `score.json` indistinguishable from an honest entry.

| # | Finding | Severity | Impact | Who can execute | Reachable | Status |
|---|---|---|---|---|---|---|
| V1 | Translation-tiling comb polyomino evades both gate layers, scores 5.0–5.999999 | **High** | Board-integrity collapse at the top: a plane tiler holds the #1 score above the legitimate class record (4), indistinguishable from a research-grade entry | Any participant; no privileges needed — plain text upload | yes (pure text) | confirmed, PoC |
| V2 | Iamond gate structurally absent for n ≥ 10; side-4 triangle tiler scores 3.0 | **High** | Same class as V1 for the iamond grid: any ≥ 10-cell tiler takes board positions at will | Any participant; no privileges needed — plain text upload | yes (pure text) | confirmed, PoC |
| V3 | Symlinked `best.heesch` → host-file read, first-token content echoed into CI logs (≤ ~1 MB/run) | **Medium** | Confidentiality: any runner-readable file's first line lands in CI logs/artifacts; doubles as a host-path existence oracle | Any participant, **if** Yukon materializes their upload as a symlink commit | conditional | confirmed, PoC |
| V4 | In-cap algorithmic burn: L=64 nested-ring witness ≈ 380 s per submission | **Medium** | Availability/cost: ~3 800× baseline runner burn per push; pipeline starvation; no score effect | Any participant; plain text upload | yes (pure text) | confirmed, measured |
| V5 | Symlink → character device → unbounded read → SIGKILL OOM (unstructured crash) | Low | Availability/robustness: host memory pressure + unstructured kill (no `REJECTED` line); still fail-closed | Any participant, same symlink precondition as V3 | conditional | confirmed, measured |
| V6 | Unbounded attacker token echo in parser errors (≤ 1 M chars) — V3's amplifier | Low | Log integrity: up to 1 MB attacker-controlled bytes per error line into logs | Any participant (own submission only) | yes | confirmed |
| V7 | `#DEFECT` marker token never validated (`#DEFECTXYZ …` accepted and scored) | Low | Format conformance: out-of-spec bytes accepted as a defect block; no score effect | Any participant | yes | confirmed |
| V8 | `MAX_LINE_CHARS` not enforced on trailing lines | Low | Conformance/robustness: oversized trailing lines silently accepted; misleading error code on the peek path | Any participant | yes | confirmed |

## V1 — Plane-tiling comb scores 5.0 (High)

**Root cause.** Layer-1 of `IsohedralGate` is skipped when the boundary word
exceeds `MAX_BOUNDARY = 160` (`boundary.py`, `gates.py`); layer-2
(`known_tilers.json`) covers only polyominoes ≤ 8 cells. Both gaps documented
— but the register assumed exploitation needs "an exotic tiler". It does not.

**PoC (executed).** A 132-cell comb (columns `x ∈ [0,12)`, 11 cells each, odd
columns shifted by 6; span 29, exactly at cap) tiles the plane by pure
translation (lattice `(12,0) × (0,11)`). Boundary word = 178 > 160 → criteria
skipped; 132 cells → not in the table. Result: `score 5.0`, `gate_tier`
byte-identical to an honest non-tiler's.

**Fix (shipped).** A ≤ 200-cell polyomino has perimeter ≤ 2n+2 = 402
(polyhex ≤ 4n+2 = 802). Raise the caps to **410 (O) / 810 (H)** so layer-1
never skips a legal shape; emit a distinct `gate_detail` for INCONCLUSIVE
entries so the board can segregate unproven scores.

## V2 — Iamond gate absent for n ≥ 10 (High)

**Root cause.** `IsohedralGate.check` returns INCONCLUSIVE unconditionally for
grid `I` after the table lookup; the table covers n ≤ 9. Every iamond tiler
with ≥ 10 cells evades by construction.

**PoC (executed).** Side-4 equilateral triangle (16 unit triangles) scores 3.0;
side-5/6 push arbitrarily higher with the same recipe.

**Fix.** Interim: `gate_detail = unchecked:iamond_beyond_table` segregates the
class on the board. Real fix: implement iamond boundary words (`boundary.py`).

## V3 — Symlinked `best.heesch` → host-file read + content exfil (Medium)

**Root cause (two parts).** (a) `_strict_load_text` (`harness/verify.py`) calls
`read_bytes()` with no `lstat`/regular-file check; a commit can carry
`submission/best.heesch` as a symlink. (b) Two parser error sites interpolate
the entire first token untruncated (`parse.py`).

**Fix.** In `_strict_load_text`, require a regular file (`os.lstat` +
`S_ISREG`, or `os.open(..., O_NOFOLLOW)`); truncate file-derived error tokens
to `[:80]`; harden the workflow surface check to reject non-regular files.

## V4 — In-cap algorithmic burn: ~380 s per submission (Medium)

**Root cause.** `MAX_LEVELS = 64` × stage-5c per-level rebuild of
`contact_neighbors` over the whole accumulated patch + 64 padded-bbox flood
fills. A 196-cell nested-ring witness burns ~170–380 s e2e, fully valid at
every level, ~3 800× baseline — always fails closed.

**Fix.** A per-run work budget (Σ|level_cells|) inside `check_corona` raising
`RESOURCE_EXCEEDED` (no epoch change). Deferred: lower `MAX_LEVELS` toward the
corona search cap of 12 (epoch bump).

## V5 — Symlink → character device → unstructured OOM crash (Low)

`read_bytes()` reads until EOF; `/dev/zero` never EOFs. 3.3 GB in 0.31 s →
SIGKILL, no `REJECTED` line. The V3 `S_ISREG` check closes it; belt-and-braces
`f.read(MAX_SHAPE_BYTES + 1)`.

## V6 — Unbounded token echo in parser errors (Low)

`parse.py` embeds full attacker tokens (≤ 1 M chars) in `VerifyError`
messages. The amplifier that makes V3 a bulk channel. Fix: `[:80]` everywhere.

## V7 — `#DEFECT` marker token never validated (Low)

`parse.py` checks only the prefix (`startswith("#DEFECT")`); `dtoks[0]` is
never compared to `"#DEFECT"`. `#DEFECTXYZ 2 67 67 67` is accepted (all fields
re-derived, so no inflation). `cli.py` uses the same prefix test for
`--emit-epoch`. Fix: require `dtoks[0] == "#DEFECT"` in both places.

## V8 — `MAX_LINE_CHARS` gap on trailing lines (Low)

`assert_exhausted` (`parse.py`) never enforces the 1 M-char line cap; the
defect peek swallows "line too long" as generic trailing garbage. Fix: enforce
the cap in `assert_exhausted` and re-raise the length error in the peek.

---

# Second pass — deep sweep (2026-08-12)

Method: eight parallel sub-agents on Critical/High hypotheses not exhausted by
pass one. The verifier/encoder core held everywhere. All new findings are in
the CI layer or the record (proof) tier.

| # | Sev | Finding | Exploitable today? |
|---|---|---|---|
| V9 | **High** | `ci.yml` runs on every push (no branch filter / surface check), default-permissions token, persisted credentials, mutable tags — pip/build/pytest execute the pushed tree | Trigger: yes; RCE: conditional on the platform gap |
| V10 | Medium | `ci.yml` pytest runs the participant's hostile `best.heesch` through the full verifier unsandboxed; valid submissions turn CI red (score == 1.0 assert on the live baseline) | Yes (exposure) |
| V11 | Medium | `ci.yml` amplifies V4: 4 jobs × ~5 harness runs × 300 s, no concurrency group, 45-min timeouts | Yes |
| V12 | Medium | `benchmark.yml` surface check is file-type blind (symlink / gitlink / plain-file all pass) | Conditional (V3 precondition) |
| F1 | High (record-tier-only) | `lrat-check` vacuously forgeable: `N 0 0` → `c VERIFIED` on any formula | No — gate disabled |
| F2 | High (record-tier-only) | Record tier silently drops the formally-verified-checker requirement when `cake_lpr` is absent (`lrat-check` fallback) | No — gate disabled |
| F3 | High-cond (record-tier-only) | drat-trim argv injection via bare-filename `proof_path` (`-S` → stdin forgery, `-D` deletes the proof) | No — hypothetical |
| F4 | Medium (record-tier-only) | Unstructured `UnicodeDecodeError` crash on checker-echoed hostile proof bytes | No — gate disabled |
| F5 | Medium (record-tier-only) | Honest trivially-UNSAT records unrecordable when `cake_lpr` is absent | No — gate disabled |

`benchmark.yml` was already hardened in the prior review round (read-only
token, `persist-credentials: false`, SHA-pinned actions, concurrency group,
surface check); `ci.yml` was not — V9–V11 close that gap.

F1–F3 are record-tier launch blockers: require `cake_lpr` (no `lrat-check`
fallback for the formally-verified slot), reject `-`-prefixed proof basenames
+ `stdin=DEVNULL`, `errors="replace"` on checker output, and synthesize the
trivial-UNSAT LRAT line — in addition to the already-registered sandboxing.

## Prioritized fix plan

1. Close the gate gap (V1/V2) — caps 410/810 + `gate_detail` marker; iamond
   boundary words.
2. Regular-file check + bounded read in `_strict_load_text` (V3/V5), `[:80]`
   truncation on the echo sites (V6), file-type surface check (V12).
3. `ci.yml` hardening (V9–V11) — branch filter, `contents: read`,
   `persist-credentials: false`, SHA-pinned actions, concurrency group,
   baseline decoupled from the live submission.
4. `check_corona` work budget (V4).
5. Parser hygiene: exact `#DEFECT` match (V7), trailing-line length (V8).
6. Record-tier blockers (F1–F5), before enabling `ProofCarryingGate`.
