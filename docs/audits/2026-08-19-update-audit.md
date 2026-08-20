# Updated Audit of `Layr-Labs/heesch-challenge`

> Historical record (2026-08-19); superseded by `docs/STATUS.md`. File
> references may be stale.

- **Audit date:** 2026-08-19
- **Repository:** [Layr-Labs/heesch-challenge](https://github.com/Layr-Labs/heesch-challenge)
- **Previously audited revision:** [`e50e6cad940431b21e055c3b575690cdf217bb92`](https://github.com/Layr-Labs/heesch-challenge/tree/e50e6cad940431b21e055c3b575690cdf217bb92)
- **Updated revision reviewed:** [`4f2634bcbf94f9794c70752dc5fdc54c9a41740b`](https://github.com/Layr-Labs/heesch-challenge/tree/4f2634bcbf94f9794c70752dc5fdc54c9a41740b)
- **Upstream comparison:** [old revision to updated revision](https://github.com/Layr-Labs/heesch-challenge/compare/e50e6cad940431b21e055c3b575690cdf217bb92...4f2634bcbf94f9794c70752dc5fdc54c9a41740b)
- **Earlier local report:** [`HEESCH_CHALLENGE_COMPARATIVE_AUDIT.md`](HEESCH_CHALLENGE_COMPARATIVE_AUDIT.md)

## Executive verdict

The updated repository is a **major and credible improvement** over the version audited previously. The two earlier critical defects have been addressed:

1. the enabled benchmark now fails closed unless non-tiling is supported by either the bounded published census or a checked UNSAT certificate; and
2. the multilevel proof path is now wired into the actual harness, with real DRAT/LRAT checking and a formally verified checker in the record path.

I did **not** find a new direct route by which a submitted tiler can receive a score without census evidence or a checked proof, assuming the multilevel encoder theorem is correct. This is a substantial change in trustworthiness. The upstream project is now materially stronger than our current `Submission_package` for validating an adversarial high-Heesch submission.

The repository is nevertheless **not fully clean or record-ready without qualification**. The most important remaining matters are:

- the standard proof band cannot handle the mathematically legitimate case `Hc = 5, Hh = 6`, and `record_eligible` unnecessarily requires an exact value rather than a certified record-breaking lower bound;
- the public record count in the README omits one of Kaplan's six `Hc = 4` polyhexes;
- several hostile or misconfigured proof inputs still cause unstructured exceptions instead of stable rejection;
- declared proof format is not matched against detected proof format, producing false provenance metadata;
- `tools/prove.py --out` can write outside the submission directory or overwrite `best.heesch` before it discovers that the name is illegal;
- the nominal 600-second encoding alarm actually covers encoding **and** proof checking, contradicting the advertised checker budgets;
- proof-size limits and a few other operational statements have drifted between code and documentation; and
- the geometric soundness of encoder revision 2 remains conditional on obligations M1/M2/M4/M5/M9 that the maintainers themselves say still require external review.

These are mostly **false-negative, availability, provenance, and documentation problems**, not a demonstrated false-positive acceptance exploit. The distinction is important.

## Scope and method

I performed the following work:

1. fetched the updated upstream repository and pinned the review to commit `4f2634b`;
2. compared it with the previously audited commit `e50e6ca`;
3. reviewed the harness, census gate, constructive tiler gates, witness verifier, parser, proof materialization, multilevel encoder interface, core-CNF path, checker wrappers, helper tools, specifications, threat model, and CI configuration;
4. ran the full local test suite and targeted proof-path tests;
5. checked the public Linux CI run using the real proof checkers;
6. repeated adversarial probes against malformed cores, mismatched proof formats, checker executability, and unsafe `prove.py` output names; and
7. compared the resulting guarantees with the current files in our `Submission_package` and `src/verify.cpp`.

The update consists of two commits:

| Commit | Main purpose |
|---|---|
| [`a58e13b`](https://github.com/Layr-Labs/heesch-challenge/commit/a58e13b16f18efe4b17f882e9301b2b2c5099ccc) | Fail-closed acceptance, complete small census, enforced proof path, specifications, threat model, and response to the earlier audit |
| [`4f2634b`](https://github.com/Layr-Labs/heesch-challenge/commit/4f2634bcbf94f9794c70752dc5fdc54c9a41740b) | Streamed record-scale encoding, core-CNF checking, proof-generation helper, and revision naming/hardening |

The aggregate change is large: **77 files changed, 21,483 insertions, and 1,621 deletions**.

## Status of the previous audit findings

| Previous external finding | Updated status | Assessment |
|---|---:|---|
| Critical 1: enabled scorer accepted finite-corona witnesses without proving non-tiling | **Closed** | The harness now rejects `TILER` and rejects `INCONCLUSIVE` unless a checked proof is supplied. |
| Critical 2: advertised record-tier proof gate was not operational | **Closed** | `ProofCarryingGate` is called by the scoring harness; checkers and proof metadata are enforced. |
| High 3: documentation understated the tiler-gate gap | **Closed** | The fail-closed rule and the limited role of constructive tiler criteria are now explicit. |
| High 4: essential CNF and verifier specifications were absent | **Closed** | Architecture, v1/v2 CNF specifications, soundness note, threat model, and feasibility documents were added. |
| High 5: v1's per-patch quantifier error was mixed with the claimed v2 result | **Closed** | The v1 inference is expressly withdrawn for `k >= 1`; only v2 is accepted. |
| Medium 6: record statement lacked a precise class qualifier | **Mostly closed** | The class is now correctly restricted to unmarked polyominoes, polyhexes, and polyiamonds, but the README's count of known `Hc = 4` examples is wrong. |
| Medium 7: “re-derives every claim in milliseconds” overstated the enabled result | **Closed** | The documentation now distinguishes fast witness checking from expensive proof generation/checking. |
| Medium 8: manifest summary and real search domain differed | **Closed in substance** | The accepted grids, census bounds, proof bands, and fail-closed behavior are now stated. Some manifest and resource-policy metadata has since drifted; see below. |

## Confirmed improvements

### 1. Acceptance now fails closed

The decisive improvement is in [`harness/verify.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/harness/verify.py#L164-L244):

- a constructive `TILER` verdict is rejected;
- a census-listed non-tiler may score;
- an out-of-census shape without a proof is rejected as `GATE_INCONCLUSIVE`;
- a present but broken proof is rejected rather than ignored; and
- successful output records `non_tiler_evidence`, proof metadata, exactness status, and the gate detail.

This repairs the earlier benchmark-level logical flaw. “No tiling found” is no longer treated as non-tiling evidence.

### 2. A complete bounded census layer was added

`heesch_verify/known_nontilers.json` contains 3,943 published small non-tilers:

| Grid | Census bound | Stored non-tilers |
|---|---:|---:|
| Polyomino (`O`) | 10 cells | 1,611 |
| Polyhex (`H`) | 8 cells | 422 |
| Polyiamond (`I`) | 12 cells | 1,910 |

For a hole-free shape inside these bounds, membership means `NON_TILER`; absence means `TILER`. The update also added enumeration-based regression tests. The exact old audit probes that previously found 89 missed 9-omino tilers, 37 missed 7-hex tilers, and 79 missed 10-iamond tilers now report zero misses.

This layer is computational evidence imported from Kaplan's published census, not a standalone proof certificate. The repository now says so explicitly.

### 3. Multilevel UNSAT proofs are enforced

The harness accepts the multilevel formula `F(S,m)`, not the old formula tied to one submitted inner patch. The asserted implication is:

\[
F(S,m)\text{ UNSAT}
\Longrightarrow
H_h(S) \le m-1
\Longrightarrow
S\text{ does not tile the plane}.
\]

Combined with a verified lower-bound witness:

- `m = hh_verified + 1` proves `Hh` exactly;
- if additionally `hc_verified = hh_verified`, it proves `Hc = Hh` exactly; and
- a larger `m` still certifies finite non-tiling but does not make the lower-bound witness exact.

The update correctly identifies the encoder as the mathematical trust boundary: a DRAT/LRAT checker proves that a CNF is UNSAT, not that the CNF faithfully models coronas. See the pinned [`soundness-note.md`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/docs/soundness-note.md#L1-L73).

### 4. The checker policy is substantially stronger

The record path now requires two verdicts:

| Submitted proof | Enforced route |
|---|---|
| DRAT | `drat-trim` verifies and converts to LRAT, then `cake_lpr` verifies the LRAT |
| LRAT | `cake_lpr` verifies first, then `lrat-check` verifies independently |

The code explicitly prevents `lrat-check` from substituting for the formally verified slot. Success strings are line-anchored, `NOT VERIFIED` overrides apparent success, standard input is closed, and checker sources/actions are pinned.

### 5. Core-CNF checking is mathematically sound in principle

For a submitted clause set `C` and regenerated formula `F`, the checker verifies every clause of `C` is literally a clause of `F`, writes a fresh CNF from the verifier's own formula lines, and checks a proof that `C` is UNSAT. Since

\[
C \subseteq F \quad\text{and}\quad C\text{ is UNSAT}
\quad\Longrightarrow\quad
F\text{ is UNSAT},
\]

this optimization is sound and can reduce checker memory substantially. The important exact-membership condition is implemented in [`core.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_encoder/proofcheck/core.py#L1-L28).

### 6. Record-scale encoding is streamed

The multilevel encoder can write DIMACS incrementally rather than materializing millions of clauses in Python objects. This is an important practical improvement for `F(S,5)` and `F(S,6)` instances.

### 7. Constructive tiler rejection was strengthened

The repository retains sound boundary-word criteria and adds a bounded toroidal exact-cover search. A returned periodic solution is rechecked as an exact partition. Failure to find such a solution remains `INCONCLUSIVE`, not `NON_TILER`. This is the correct direction of asymmetry for a fail-closed verifier.

### 8. Security and reproducibility improved

Notable additions include:

- refusal of symlinks and non-regular submission files;
- bounded shape reads and xz decompression;
- digest and header checks;
- stale-score deletion before fallible work;
- sandboxed benchmark execution where supported;
- no execution or import of participant code;
- deterministic encoding manifests and golden digests; and
- many more parser, proof, census, periodic, and hostile-input tests.

## Test evidence

### Local tests on macOS

The full test suite, before local real-checker setup, completed as:

```text
481 passed, 29 skipped in 379.91s
```

After building host `drat-trim` and `lrat-check`, I ran the targeted proof/core suite using the repository's documented macOS test shim for the Linux-only CakeML executable:

```text
49 passed in 156.47s
```

Python byte-compilation also completed successfully:

```text
compileall=ok
```

`git diff --check` found only intentional Markdown hard-break spaces in the copied historical audit, not a source-code whitespace defect.

### Public Linux CI with real checkers

The upstream [GitHub Actions run 32100368078](https://github.com/Layr-Labs/heesch-challenge/actions/runs/32100368078) succeeded for commit `4f2634b` on Ubuntu and Windows with Python 3.11 and 3.12. The Ubuntu 3.12 job reported:

```text
502 passed, 8 skipped in 688.63s
33 proof-gate/census tests passed in 401.57s
harness end-to-end: score 1.0, evidence census
```

The Linux job built and used the real x86-64 `cake_lpr`, so it is stronger evidence than the local macOS shim run.

### Docker status

The local Docker daemon was not available during this audit:

```text
failed to connect to the docker API at unix:///Users/airbartek/.docker/run/docker.sock
```

I therefore did not claim a fresh local Docker execution. The successful upstream Linux CI covers the primary Linux checker path.

## Remaining findings

## High 1: the automatic record path excludes a legitimate `Hc = 5, Hh = 6` case

### Problem

For any polyform,

\[
H_c(S) \in \{H_h(S)-1, H_h(S)\}.
\]

Therefore a record-breaking shape with `Hc = 5` may have either `Hh = 5` or `Hh = 6`.

The repository repeatedly says that “an `Hc = 5` certificate is `F(S,6)`.” That is true only when `Hh <= 5`. If the genuine shape has `Hc = 5, Hh = 6`, then a real six-corona exists, so a sound `F(S,6)` must be SAT. A finite upper certificate requires at least

\[
F(S,7)\text{ UNSAT},
\]

which gives `Hh <= 6`.

The standard harness band is:

```python
((12, 6), (20, 5), (50, 3), (100, 2))
```

and the encoder feasibility band also rejects `m = 7` for every cell count. See [`proofgate.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_verify/proofgate.py#L54-L73) and [`multilevel/api.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_encoder/multilevel/api.py#L53-L77).

### Additional classification error

Even if an `F(S,7)` proof were checked out of band, the current code sets:

```python
record_eligible = exact and evidence == "proof" and hc_verified >= 5
```

An exact `Hc` value is not necessary to establish a new record. A verified witness `Hc >= 5` plus any sound finite upper bound on `Hh` already proves that the shape is a finite non-tiler whose `Hc` beats the known value 4. For example,

\[
H_c \ge 5,\qquad H_h \le 6
\quad\Longrightarrow\quad
H_c\in\{5,6\},
\]

and either value is record-breaking.

### Consequence

This is a **false-negative and classification defect**, not a false acceptance. The benchmark may reject or fail to flag a legitimate record construction precisely because its hole-permitted Heesch number is one larger than its hole-free value.

### Recommended fix

1. Separate `record_breaking_lower_bound` from `exact_record`.
2. Define the former as checked non-tilerhood plus `hc_verified >= 5`.
3. Support `m = 7` at least in the out-of-band path, with measured limits.
4. If exact `Hc = 5` is required, add a distinct hole-free upper-bound certificate; `F(S,m)` currently bounds `Hh`, not `Hc` directly.
5. Replace the unconditional “an `Hc = 5` certificate is `F(S,6)`” wording with the precise `Hh = 5` condition.

## High 2: `tools/prove.py --out` can escape the submission directory or destroy the input

### Problem

The help text calls `--out` a basename, but the tool does not validate it before doing expensive work and writing the result. Validation occurs only indirectly when the newly generated `#PROOF` block is parsed at the end.

Two isolated reproductions showed:

1. `--out ../escaped.lrat` wrote a 257,099-byte file outside the submission directory and only then failed on the illegal proof name.
2. `--out best.heesch` overwrote the shape input with LRAT bytes and only then failed because `best.heesch` is forbidden as a proof filename.

The relevant order is visible in [`tools/prove.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/tools/prove.py#L248-L416): `name` is accepted at line 299, the final proof is written at lines 399–406, and `parse_submission(new_text)` is not called until line 415.

The helper also uses one persistent `.prove-tmp` directory, so concurrent runs can race. Solver failures leave large CNF/proof intermediates behind; a failed test with a nonexistent solver left a roughly 1.5 MB formula, and record-scale leftovers could be gigabytes.

### Consequence

This does not compromise the remote verifier, because the harness never executes participant code or `prove.py`. It is nevertheless a serious operator/participant safety bug in the repository's official proof-production workflow.

### Recommended fix

- validate the requested basename, suffix, compression, collision with `best.heesch`, and parent directory before encoding;
- use `TemporaryDirectory(dir=dest_dir)` rather than a shared `.prove-tmp`;
- install outputs atomically only after all self-checks and parser checks pass; and
- clean temporary files in `finally` on every exit path.

## Medium 3: non-ASCII core data crashes the proof gate

### Problem

`parse_core_file()` opens the participant-controlled core with strict ASCII decoding, but does not translate `UnicodeDecodeError` or `OSError` into `CoreError`. The pipeline catches only `CoreError`.

A core beginning with byte `0xff` produced:

```text
UnicodeDecodeError: 'ascii' codec can't decode byte 0xff ...
```

instead of a structured `GATE_PROOF_INVALID` rejection. See [`core.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_encoder/proofcheck/core.py#L69-L103) and the narrow exception handler in [`pipeline.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_encoder/proofcheck/pipeline.py#L231-L248).

### Consequence

No invalid submission receives a score, but hostile input can turn a stable fail-closed rejection into an unstructured harness crash.

### Recommended fix

Catch decoding and file-I/O exceptions at the parser boundary and return `GATE_PROOF_INVALID` or `RESOURCE_EXCEEDED` as appropriate. Add binary/non-ASCII regression cases.

## Medium 4: declared proof format is not enforced and accepted provenance can be false

### Problem

The submission parser checks that the filename suffix matches the declared `drat|lrat`, but `ProofSubmission` carries no declared format. The proof pipeline independently sniffs the actual bytes and dispatches according to the detected format. The final `ProofVerdict`, however, records the submitter's declaration.

I supplied a valid LRAT proof under a `.drat` filename and declared it as DRAT. The gate accepted it using the LRAT route (`cake_lpr` and `lrat-check`) but emitted:

```json
{
  "status": "VERIFIED",
  "format": "drat",
  "checkers_verified": ["cake_lpr", "lrat-check"]
}
```

The proof remains mathematically checked, so this is not a false UNSAT verdict. It is nevertheless false audit metadata and violates the submission schema.

### Recommended fix

Carry the declared format into `ProofSubmission`, compare it with the sniffed class, reject mismatches, and store both declared and detected formats if both are useful diagnostically.

## Medium 5: the 600-second “encoding” alarm covers the checkers too

### Problem

`ENCODE_TIMEOUT_S = 600` is documented as an encoding guard. In practice, the context manager wraps the entire call to `check_proof_v2()`, and that call performs both encoding and all external checker runs. See [`proofgate.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_verify/proofgate.py#L247-L333).

The checker budget separately advertises:

| Checker | Per-checker cap |
|---|---:|
| `drat-trim` | 600 s |
| `cake_lpr` | 900 s |
| `lrat-check` | 300 s |
| Overall checker deadline | 1,500 s |

The outer SIGALRM therefore makes the 900-second and 1,500-second policies unreachable on POSIX: encoding plus all checker work is killed at 600 seconds.

### Consequence

Legitimate record-scale proofs can be rejected as `RESOURCE_EXCEEDED` earlier than the published policy says. This is another false-negative/availability issue.

### Recommended fix

Apply the alarm only around `encode_multilevel_stream`, or replace the nested limits with one clearly documented end-to-end deadline and pass the remaining time to each checker.

## Medium 6: proof bytes are materialized before the claimed CNF is rejected

### Problem

The proof-pipeline specification says the CNF is regenerated and its digest checked “before touching any submitted proof bytes.” The outer harness gate instead decompresses and hashes the proof and optional core first, then calls the pipeline that regenerates the CNF.

The actual order is visible in [`proofgate.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_verify/proofgate.py#L279-L328), whereas [`pipeline.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_encoder/proofcheck/pipeline.py#L1-L19) documents the reverse order.

### Consequence

A submission with an obviously false CNF digest can force up to the decompression cap of proof/core work before the cheap mismatch is returned. This is bounded, so it is not an unbounded decompression attack, but it violates the stated threat-model ordering and spends avoidable resources.

### Recommended fix

Regenerate and compare the CNF digest/header before materializing the proof, or correct the specification and justify the chosen order.

## Medium 7: a non-executable checker passes preflight and then crashes

### Problem

`missing_checkers()` tests only whether each checker path is a regular file. `_run()` tests only existence. Neither checks execute permission, and `subprocess.run()` does not catch `PermissionError`/`OSError`.

Three regular mode-`0644` placeholder checker files passed preflight and then produced:

```text
PermissionError: [Errno 13] Permission denied: .../cake_lpr
```

See [`proofgate.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_verify/proofgate.py#L226-L245) and [`checkers.py`](https://github.com/Layr-Labs/heesch-challenge/blob/4f2634bcbf94f9794c70752dc5fdc54c9a41740b/heesch_encoder/proofcheck/checkers.py#L120-L163).

### Consequence

The normal Linux setup checks executable binaries, so this is mainly an operator/misconfiguration robustness defect. It still contradicts the stable fail-closed error contract.

### Recommended fix

Require `os.access(path, os.X_OK)` in preflight and convert spawn-time `OSError` into `CHECKER_UNAVAILABLE`.

## Medium 8: the README miscounts the known `Hc = 4` polyhexes

### Problem

The README says there are five `Hc = 4` polyhexes of sizes 11, 13, 15, 15, and 16, plus one 20-iamond. Kaplan's cited exhaustive table contains **six** such polyhexes:

| Polyhex size | Count with `Hc = 4` |
|---:|---:|
| 11 | 1 |
| 13 | 1 |
| 15 | 2 |
| 16 | 1 |
| 17 | 1 |
| **Total** | **6** |

There is also one 20-iamond with `Hc = 4`, so the cited computation contains seven `Hc = 4` unmarked polyforms in these three lattice families. The omitted example is the 17-hex. See Kaplan's [paper](https://arxiv.org/abs/2105.09438) and the included source table at `docs/arXiv/arXiv-2105.09438v1/unmarked.tex:782` in this repository.

### Recommended fix

Change the README list to `11, 13, 15, 15, 16, 17`, and say “six polyhexes and one 20-iamond.”

## Medium 9: the claimed “essentially unexplored” band begins too early

### Problem

The README calls the entire proof-required band—11–200 ominoes, 9–200 hexes, and 13–200 iamonds—“essentially unexplored.” Those are the benchmark's **census cutoff** values, not the literature's exhaustive-search cutoff values.

The cited Kaplan computation is exhaustive through:

- 19-ominoes,
- 17-hexes, and
- 24-iamonds.

Therefore the ranges 11–19, 9–17, and 13–24 are not unexplored merely because the benchmark chose not to embed their enormous full census tables.

### Recommended fix

Distinguish the **embedded exact-census band** from the **published exhaustive-search band**. A defensible formulation is that the large tail beyond 19/17/24 remains broadly unexplored, subject to any later literature.

## Low-severity drift and cleanup findings

### 10. Runtime and documented proof-size caps disagree

The code accepts a decompressed proof payload up to **1 GiB**. The README, architecture document, and threat-model control C7 still say **256 MiB**. The threat model later says 1 GiB in its availability section, contradicting itself.

Choose one limit and update every occurrence. If 1 GiB is intended, document the disk and time implications explicitly.

### 11. The README grammar omits the optional `core` line

`tools/prove.py` emits a core by default and the prose discusses it, but the main file-format code block ends after the `file` line. Add:

```text
core <basename> <none|xz> <payload_sha256> <num_clauses>
```

### 12. Revision-2 manifest records a stale checker policy

`heesch_encoder/revisions/rev-2.json` says:

```json
["cake_lpr-or-lrat-check", "drat-trim"]
```

The enforced code correctly disallows that fallback: `cake_lpr` is mandatory. The multilevel specification calls the manifest field “documentary and superseded,” but an immutable revision manifest should not contain false provenance. Add a corrected revision/addendum rather than silently changing an already frozen digest.

### 13. `defect_board_enabled` disagrees with actual scoring

`VerifyConfig.defect_board_enabled` defaults to `False`, and the architecture lists public defect ranking as an open question. Nevertheless, the harness always verifies a submitted defect block and `yukon_score()` always adds its fraction. The emitted result can therefore say `defect_enabled: false` while the score includes defect credit.

Either remove the dead flag and update the architecture, or make scoring honor it. The current README and benchmark description indicate that defect scoring is intended to be active.

### 14. Historical response text has stale operational values

The response document says `maxSubmissionBytes = 64 MiB`; `benchmark.json` now uses 128 MiB. Its reproduction section says `tier: record`, but the actual schema values are `lower_bound` and `exact_proof`.

### 15. CakeML heap comment and implementation disagree

The comment says the automatic heap uses 70% of `MemAvailable`; the code uses 85%. This is minor but should be corrected because it affects resource planning.

## Mathematical trust boundary still requiring review

The updated project is commendably explicit that proof checking alone is insufficient. A checked DRAT/LRAT file establishes only:

\[
F(S,m)\text{ is UNSAT}.
\]

The geometric conclusion requires the implication:

\[
\text{a real hole-permitted }m\text{-corona}
\Longrightarrow
\text{a satisfying assignment of }F(S,m).
\]

The repository decomposes this into obligations including:

- **M1:** every placement needed by any real corona is present in the generated universe;
- **M2:** every real corona is a weak configuration;
- **M4:** every weak configuration extends to a satisfying assignment;
- **M5:** auxiliary encodings preserve satisfiability; and
- **M9:** the regenerated CNF is exactly the intended frozen formula.

The test suite gives substantial empirical support, including round trips and 46/46 known exact cases. It is not a formal proof of M1/M2/M4 for every admissible shape. The upstream soundness note explicitly says external review remains open. Until that review is completed, a record result should be described as:

> accepted by the revision-2 verifier and its checked UNSAT proof, conditional on the stated encoder soundness obligations.

This is not a newly discovered defect; it is the correct residual trust boundary.

## Comparison with our current project

The updated Layr Labs repository has overtaken our current challenge package in adversarial verification quality.

| Capability | Updated Layr Labs repository | Our current repository |
|---|---|---|
| Submitted witness geometry | Independently derives levels, contact, surround, holes, and symmetry validity | `src/verify.cpp` checks overlap and holes but does not recompute complete corona/surround validity |
| Non-tiler acceptance | Fail-closed census or checked multilevel UNSAT proof | No general non-tiler certificate; absence of an isohedral tiling is explicitly weaker |
| Tiler handling | Census and constructive tiling witnesses reject; inconclusive remains inconclusive | `sat -isohedral` finds only supported tiling classes; no full non-tiler proof |
| Proof artifacts | DRAT/LRAT, pinned checkers, formally verified checker slot, CNF digest | None |
| Record metadata | Lower-bound/exact distinction and evidence provenance | Final `YES/NO` wrapper with weaker semantics |
| Search/classification engine | Python verifier plus bounded constructive filters | Mature C++ `heesch-sat` search is useful as an independent exploration and cross-check tool |

Two local limitations remain particularly important:

1. [`src/verify.cpp`](src/verify.cpp) claims that it checks that the halo is filled appropriately, but the implementation only accumulates occupied cells, rejects overlaps, and invokes `HoleFinder`; it does not independently reconstruct corona levels or establish every surround condition.
2. [`Submission_package/README.md`](Submission_package/README.md) correctly warns that `YES` does not prove non-tiling beyond the isohedral class. Consequently, that package cannot by itself validate a finite record Heesch number.

Our current prompt also targets `Hc >= 7` by importing the value 6 from a broader class of planar shapes. For the challenge's stated unmarked polyomino/polyhex/polyiamond class, Kaplan's cited record is `Hc = 4`, so the first record-breaking target is `Hc >= 5`. The external repository now frames this class distinction more accurately, apart from the count error described above.

## Recommended combined workflow

The strongest practical architecture would use both projects but assign them different roles:

1. **Search:** use our C++ `gen`, `sat`, and visualization tools to generate and explore candidates efficiently.
2. **Independent lower-bound check:** run our C++ solver and the external geometric verifier separately on the submitted witness.
3. **Fail-closed non-tiler certificate:** require the external census evidence or a revision-pinned multilevel UNSAT proof.
4. **Proof checking:** run `cake_lpr` plus the appropriate independent checker in a resource-isolated Linux environment.
5. **Record review:** independently inspect M1/M2/M4/M5/M9, regenerate the CNF, recheck proof and witness on a second machine, and publish all hashes and artifacts.
6. **Record classification:** distinguish a certified record-breaking lower bound (`Hc >= 5`, finite) from an exact value (`Hc = 5`).

Our C++ solver should be treated as a valuable independent search/cross-check engine, not as a substitute for a proof-carrying non-tiler gate.

## Required fixes before production deployment

### Must fix

1. Validate and atomically handle `tools/prove.py --out`; prevent path escape and input clobbering.
2. Convert non-ASCII core input and checker spawn errors into stable fail-closed verdicts.
3. Enforce declared-versus-detected proof format and correct provenance output.
4. Resolve the 600-second timeout scope so implementation matches published policy.
5. Define record eligibility by the actual contest objective: exact value or certified record-breaking lower bound.

### Should fix

6. Design and measure an `m = 7` out-of-band route for the possible `Hc = 5, Hh = 6` case.
7. Correct the `Hc = 4` count and the explored-range statement.
8. Reconcile all proof-size limits, proof grammar, manifest policy, defect flag, and response-document values.
9. Add regression tests for each reproduced malformed-input and helper-safety case.

### Required before announcing a mathematical record

10. Obtain independent review of the revision-2 encoder soundness obligations.
11. Regenerate and verify the proof outside the submission's environment.
12. Publish the shape, witness, CNF revision/digest, proof digest, core, checker versions, and full verification log.
13. Cross-check the candidate with an independent implementation such as our C++ `heesch-sat` workflow.

## Final assessment

The update successfully addresses the central criticism of the earlier audit. The project has changed from a strong finite-witness checker with an unsound benchmark acceptance rule into a **genuinely fail-closed, proof-carrying verification pipeline**.

The enabled acceptance rule now appears logically coherent:

\[
\text{verified lower-bound witness}
+
\text{census or checked finite upper certificate}
\Longrightarrow
\text{finite certified Heesch lower bound}.
\]

I found no demonstrated route to a false score that bypasses that rule. The principal remaining mathematical defect is incompleteness around `Hc = 5, Hh = 6` and the overly strict exactness requirement for `record_eligible`. The remaining implementation defects should be repaired before relying on the package as an unattended public adversarial verifier, but they do not erase the substantial progress made in these two commits.

**Deployment recommendation:** suitable for continued benchmark development and controlled testing now; suitable for automated scoring after the hostile-input and timeout fixes; suitable for announcing a record only after external encoder review and independent artifact re-verification.
