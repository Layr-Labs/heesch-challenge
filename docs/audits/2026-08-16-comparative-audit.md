# Comparative Audit of `Layr-Labs/heesch-challenge` and Our Heesch-SAT Challenge

**Audit date:** 2026-08-16  
**External repository:** <https://github.com/Layr-Labs/heesch-challenge>  
**External snapshot:** [`e50e6cad940431b21e055c3b575690cdf217bb92`](https://github.com/Layr-Labs/heesch-challenge/tree/e50e6cad940431b21e055c3b575690cdf217bb92), committed 2026-08-13  
**Local comparison:** current working tree of this repository, based on commit `37d61f603eedf80cfb32a9ccbac208e2ac85faae`

## Executive verdict

The Layr Labs repository is a substantial and generally careful implementation of an **independent finite-witness verifier**. Its parser, transform checks, corona reconstruction, hole checks, resource limits, stable error codes, test coverage, and hostile-input handling are materially stronger than the corresponding submitted-patch path in our current package.

However, the enabled Layr Labs benchmark is **not yet a sound verifier of a record finite Heesch number**. It verifies only a lower-bound witness, rejects tilers only when an incomplete constructive gate recognizes them, and then emits a score even when that gate is `INCONCLUSIVE`. The proof-carrying non-tiler/exactness tier described in the README is disabled, not called by the harness, and not expressible in the participant file format. Consequently:

> The enabled benchmark can score an unrecognized plane tiler. Such a shape has infinite Heesch number and therefore has every finite corona lower bound, but it is not a finite-Heesch record.

This is not merely a hypothetical concern about very large or exotic shapes. A census audit using Kaplan's published complete non-tiler data found **89 nine-omino tilers, 37 seven-hex tilers, and 79 ten-iamond tilers** that the enabled gate labels `INCONCLUSIVE` immediately beyond its lookup-table cutoffs.

Our package has the complementary profile. The original C++ `sat` search can, when it reaches an unsatisfiable next-corona instance, compute a finite Heesch value rather than merely check a submitted lower-bound witness. But our added `verify` helper does **not** independently verify corona structure, and our participant prompt currently documents the six-parameter affine transform incorrectly. Our final script largely recomputes the shape with `sat`, so it does not actually validate the AI's submitted arrangement in the strong sense promised by the challenge.

**Bottom line:** neither deployed pipeline, as currently packaged, is a complete research-record verifier. The strongest design would combine:

1. Layr Labs' independent geometry/witness verifier;
2. an all-level SAT encoding with a checked UNSAT certificate;
3. an enforced non-tiler/exactness gate rather than an out-of-band policy; and
4. the original `heesch-sat` classifier as an independent computational cross-check.

## Scope and method

The audit covered:

- the participant contract and scoring semantics;
- the geometric definitions of transforms, adjacency, coronas, holes, `Hc`, and `Hh`;
- the enabled harness and plane-tiler gate;
- the dormant CNF/proof-checking path and its soundness notes;
- automated tests and CI configuration;
- Kaplan's original paper, dataset, and source implementation; and
- our current Docker challenge, prompt, validator, and C++ `verify` helper.

The external repository was reviewed at the immutable commit above. The local repository contains uncommitted and untracked challenge-package work, so local conclusions refer to the files as they existed on the audit date, not to a clean tagged release.

## What a correct verifier must establish

Let `C_k(S, P)` mean that `P` is a valid hole-free patch containing a seed copy of a shape `S` and complete coronas through level `k`. Then

\[
H_c(S) \ge k \quad\Longleftrightarrow\quad \exists P\; C_k(S,P).
\]

A submitted valid patch is therefore enough to prove the **lower bound** `Hc(S) >= k`.

To prove the exact finite value, one also needs

\[
H_c(S) \le k
\quad\Longleftrightarrow\quad
\neg\exists P'\; C_{k+1}(S,P').
\]

The quantifier over **all** possible patches is essential. Proving that one particular `k`-patch cannot be extended does not prove that some different `k`-patch cannot be extended.

Finally, under Kaplan's convention,

\[
S\text{ tiles the plane} \quad\Longrightarrow\quad H_c(S)=H_h(S)=\infty.
\]

Thus a tiler satisfies every finite lower bound `Hc >= k`. A benchmark that accepts lower-bound witnesses may deliberately include tilers, but then it must not describe those entries as finite-Heesch records or claim that all plane tilers are rejected.

Kaplan gives the recursive surround/corona definition and sets the Heesch number of a plane tiler to infinity in [the paper](https://arxiv.org/abs/2105.09438). The project page also publishes the exhaustive data used in this audit: [Heesch Numbers of Unmarked Polyforms](https://cs.uwaterloo.ca/~csk/heesch/).

## Guarantee comparison

| Property | Layr Labs enabled harness | Our current package |
|---|---|---|
| Parses a supplied shape and witness | Yes | Yes |
| Validates legal grid symmetries | Yes, including affine lattice restrictions | No independent check in `src/verify.cpp` |
| Requires exactly one central copy | Yes | No |
| Recomputes corona levels | Yes | No |
| Rejects orphan/disconnected copies | Yes | No |
| Checks complete surround/halo coverage | Yes | No |
| Checks overlap and corona holes | Yes | Overlap and holes only |
| Proves submitted lower bound `Hc >= k` | Yes | Not from the submitted patch; `sat` recomputes separately |
| Searches for a missing next corona | Not in the enabled harness | Yes, through the C++ SAT classifier |
| Produces a checked UNSAT certificate | Dormant code exists; disabled and not integrated | No |
| Rejects every plane tiler | No; only constructively recognized tilers | A finite `~` result implies non-tiling under the trusted SAT implementation, but arbitrary tilers can remain inconclusive |
| Record/exactness policy enforced by executable code | No | Partly: acceptance requires a finite `~` result, but without proof-carrying certification |
| Hostile-input hardening | Strong | Basic |
| Automated regression suite | Extensive | Small script-level smoke suite |

## Strengths of the Layr Labs repository

### 1. The witness geometry checker is well designed

The external verifier:

- validates transforms against the selected grid's actual symmetry group, rather than accepting every determinant-`+/-1` matrix ([`transform.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/heesch_verify/transform.py#L26-L64));
- requires exactly one level-0 placement;
- materializes every tile and rejects overlap;
- recomputes levels instead of trusting participant labels;
- rejects disconnected/orphan placements;
- checks that every contact-neighbour cell of the accumulated inner patch is covered by the next corona; and
- applies the appropriate inner/outer hole rule ([`patch.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/heesch_verify/patch.py#L106-L239)).

This directly matches the logical role of a finite witness: it independently establishes `Hc >= k`.

### 2. The affine transform convention is correct

For

```text
<a,b,c,d,e,f>
```

the external repository correctly uses

\[
x' = ax+by+c, \qquad y' = dx+ey+f.
\]

That is exactly the convention in the original C++ implementation at `src/geom.h:165` and in the external [`README`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/README.md#L27-L39).

### 3. Lower bounds and heuristic scores are mostly distinguished correctly

The README explicitly says that the fractional score is not a Heesch number, and the code reports `hc_verified` separately ([`README.md`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/README.md#L47-L65), [`score.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/heesch_verify/score.py#L70-L81)). This is the correct epistemic distinction: defect reduction may guide search, but it is not a new corona and is not mathematical evidence for a larger integer Heesch number.

### 4. The repository recognizes its most important SAT quantifier bug

The soundness note correctly identifies that UNSAT for an extension formula tied to one submitted patch does not quantify over all alternative patches. It explicitly calls the old inference unsound for `k >= 1` and proposes an all-level encoding ([`soundness-note.md`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/docs/soundness-note.md#L12-L39)). Finding and documenting this issue is a significant strength.

### 5. Engineering and adversarial testing are substantially stronger than ours

The external package has bounded input reads, regular-file checks, stable error codes, canonicalization, resource budgets, sandboxed benchmark execution, pinned Python test dependencies, fuzz/metamorphic/differential tests, encoder round trips, and proof-checker hardening. At the audited commit:

```text
372 passed, 10 skipped in 95.61s
```

The skipped local cases include optional external proof checkers and bounded exhaustive configurations; the Linux CI workflow builds the proof checkers. A green suite does not resolve the benchmark-policy flaw below, but it gives the implementation a much stronger regression base than our current shell-only challenge tests.

## Critical findings in the Layr Labs repository

### Critical 1: the enabled scorer does not enforce a finite, non-tiling record

The enabled decision rule is effectively

\[
\operatorname{ValidWitness}(S,k)
\;\land\;
\operatorname{IsohedralGate}(S)\ne\texttt{TILER}.
\]

The harness rejects a shape only when the gate returns `TILER`; every `INCONCLUSIVE` result proceeds to `score.json` ([`harness/verify.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/harness/verify.py#L143-L156)). The gate itself correctly acknowledges that failure of its criteria proves nothing and returns `INCONCLUSIVE`, never `NON_TILER` ([`gates.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/heesch_verify/gates.py#L1-L9)).

This is sound if the board is explicitly a **finite-corona lower-bound board that permits tilers**. It is not sound for the repository's headline task, “Find unmarked polyforms with record Heesch numbers,” or for the manifest statement that “Plane-tilers are rejected” ([`benchmark.json`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/benchmark.json#L1-L12)).

The repository partly acknowledges that a missed tiler may score, but then says it cannot reach the record tier because a proof will be required ([`README.md`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/README.md#L67-L86)). That protection is not present in the executable harness.

#### Reproducible census audit

For the first size immediately beyond each exhaustive digest table, I:

1. enumerated all free polyforms using the repository's `tools/classify.py`;
2. removed holed shapes;
3. canonicalized Kaplan's complete published `0up` non-tiler file;
4. treated the remaining hole-free forms as tilers, following Kaplan's complete census; and
5. ran the repository's current `IsohedralGate` on every such tiler.

| Family | Free forms | Holed | Published non-tilers | Plane tilers | Gate catches | Gate misses |
|---|---:|---:|---:|---:|---:|---:|
| 9-ominoes | 1,285 | 37 | 198 | 1,050 | 961 | **89** |
| 7-hexes | 333 | 2 | 37 | 294 | 257 | **37** |
| 10-iamonds | 448 | 4 | 103 | 341 | 262 | **79** |

The non-tiler counts match Kaplan's published tables: 198 for 9-ominoes, 37 for 7-hexes, and 103 for 10-iamonds. The paper explains that tilers were removed with Myers's tiling classifier before Heesch-number computation (`docs/arXiv/arXiv-2105.09438v1/unmarked.tex:712` in our source copy).

Concrete known tilers missed by the gate include:

```text
O 0 0 0 1 0 2 0 3 0 4 0 5 0 6 1 0 1 3
digest 81ba3f2f4eedb2bc6c5fdcaa8f9d005d2a441513437c7046c135291f577f8726
gate   evaluated:no_factorization

H 0 0 0 1 0 2 0 3 0 4 1 0 1 3
digest 14f8f487156b333160b877d25748306742da22f866f5142a62920a036d54d4c0
gate   evaluated:no_factorization

I 0 0 0 3 0 6 0 9 1 1 1 4 1 7 1 10 3 9 4 7
digest 46bacd4a8480b5ebb5896b4df8658118aabd9384c702cfb3aa073b82bc3efe81
gate   evaluated:no_factorization
```

I did not construct and submit a complete depth-5 witness for one of these tilers during this audit. That is an implementation exercise, not a missing logical premise: a plane tiling provides a finite valid corona witness at every depth. Therefore any missed tiler for which the participant supplies such a patch passes the enabled mathematical acceptance condition.

### Critical 2: the advertised record-tier proof gate is not operational

The README says record claims require a machine-checked UNSAT proof. In the audited code:

- `ProofCarryingGate.ENABLED` is `False`;
- its `check` method raises when disabled and is otherwise `NotImplemented`;
- `harness/verify.py` imports and calls only `IsohedralGate`;
- the submission parser accepts witness and optional defect blocks, but no proof manifest or proof file reference; and
- the benchmark workflow reports the ordinary harness score without a promotion/proof phase.

See [`gates.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/heesch_verify/gates.py#L131-L152), [`harness/verify.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/harness/verify.py#L25-L28), and [the benchmark workflow](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/.github/workflows/benchmark.yml#L86-L101).

There is real proof-checking and multilevel-CNF code in the repository, but it is a development path, not an enforced acceptance path. An external platform may have an additional promotion policy, but that cannot be audited or relied upon from the reviewed repository. GitHub source permalinks in this report may require an account authorized to view the repository.

### High 3: the public documentation understates the tiler-gate gap

The documentation describes residual missed tilers as “large” or “very large exotic” shapes. The census above finds missed tilers at 9 squares, 7 hexagons, and 10 triangles—the first sizes beyond the tables. The code itself openly omits several constructive boundary factorization types, including reflection and additional hex rotation forms ([`gates.py`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/heesch_verify/gates.py#L97-L113)).

The correct wording is:

> Every tiler in the small committed census is rejected. Outside those census bounds, some additional tilers are rejected by sufficient boundary factorizations, while all other shapes—including many ordinary tilers—remain inconclusive and can receive a lower-bound score.

### High 4: essential proof specifications are referenced but absent

The code and documents repeatedly cite:

- `heesch-cnf-encoder-spec.md`;
- `heesch-multilevel-encoder-spec.md`;
- `architecture.md` or `verifier-architecture.md`; and
- `docs/THREAT-MODEL.md`.

None of these files is present at the audited commit. This prevents an independent reviewer from checking the exact CNF semantics, the stated M1-M9 obligations, the promotion state machine, or the complete threat model against their normative specifications.

This is especially important because the repository correctly identifies the encoder as the trust boundary: a valid DRAT/LRAT proof establishes UNSAT of the generated CNF, not that the CNF faithfully encodes all geometric configurations ([`soundness-note.md`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/docs/soundness-note.md#L1-L10)).

### High 5: the soundness note mixes the known-unsound v1 claim with the v2 status

The note first says the one-patch formula `F(S,P_k)` is unsound for exactness at `k >= 1`, then reports a new multilevel v2 encoder. Later, under “The claim,” it again states that UNSAT of `F(S,P_k)` implies no next corona and exactness ([`soundness-note.md`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/docs/soundness-note.md#L71-L79)). Read literally, that repeats the inference rejected earlier in the same document.

The document should be split into two explicitly versioned theorems:

- **v1:** sound only at `k=0` for exactness;
- **v2:** UNSAT of the all-level weak-configuration relaxation `F(S,k+1)` implies no true `(k+1)`-corona, conditional on reviewed universe-completeness and clause-relaxation obligations.

The v2 design may be sound; this audit does not claim that it is unsound. The repository itself marks it as draft and externally unreviewed. Its empirical weak-gap calibration covers 46 small exact cases, mostly `Hc <= 1`, not a record-scale `Hc=5` instance ([`ml-weak-gap.md`](https://github.com/Layr-Labs/heesch-challenge/blob/e50e6cad940431b21e055c3b575690cdf217bb92/docs/ml-weak-gap.md#L1-L12)).

### Medium 6: the record statement needs a precise class qualifier

The external headline says the class record for **unmarked polyominoes, polyhexes, and polyiamonds** is `Hc=4`. That is supported by Kaplan's exhaustive computations through 19-ominoes, 17-hexes, and 24-iamonds, which found examples up to 4 and none higher in those searched classes.

The next sentence, “5 has never been exhibited by anyone,” is misleading if detached from that class qualifier. Heesch number 5 is known for marked polyforms, and Bašić exhibited a general planar figure with Heesch number 6. See:

- [Kaplan, *Heesch Numbers of Unmarked Polyforms*](https://arxiv.org/abs/2105.09438);
- [Kaplan's data and tables](https://cs.uwaterloo.ca/~csk/heesch/); and
- [Bašić, *A Figure with Heesch Number 6*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7812982/).

Recommended wording:

> No unmarked polyomino, polyhex, or polyiamond with `Hc >= 5` is documented in the cited exhaustive search or in the literature reviewed for this benchmark.

### Medium 7: “re-derives every claim ... in milliseconds” overstates the enabled result

The harness validates a **supplied witness** and computes its lower bound; it does not derive an exact Heesch number or non-tilerhood from shape geometry alone. The verifier also deliberately allows a corona work budget corresponding to multi-second checks, with comments discussing approximately 15-second worst cases. The README should say “independently validates the supplied finite witness under bounded resources,” not “re-derives every claim ... in milliseconds.”

### Medium 8: the benchmark's actual search domain is narrower than its manifest summary

The README enforces both `<=200` cells and `span_x + span_y <= 29`, and the verifier applies that cap. The `benchmark.json` description mentions only the cell cap. Thus the nominal “20-200 cell band” excludes many elongated polyforms. This is a legitimate engineering limit, but it should appear in the top-level benchmark contract and any scientific description of the search domain.

## Critical comparison findings in our package

These are not defects in the external repository, but they materially affect any claim that our package is currently the stronger alternative.

### Our issue 1: the AI prompt gives the wrong affine formula

`Submission_package/prompt_ai.md:50` currently says

```text
x' = a*x + b*y + e
y' = c*x + d*y + f
```

and identifies `[[a,b],[c,d]]` as the matrix. The implementation actually uses

```text
x' = a*x + b*y + c
y' = d*x + e*y + f
```

with linear matrix `[[a,b],[d,e]]` and translation `(c,f)`, as shown at `src/geom.h:165`.

This must be fixed before another export. Identity-only examples hide the error, while rotated or translated nontrivial examples can be documented incorrectly.

### Our issue 2: the toy “Hc=1” domino patch is not a complete corona

The toy block at `Submission_package/prompt_ai.md:73` places only copies above and below the central domino. It does not cover the full point-contact halo and therefore does not establish a first corona. Layr Labs' verifier rejects this kind of patch with `PATCH_GAP`; our current helper can accept it because the union has no overlap or hole.

If an example is only syntactic, its status should not make a false geometric claim. Prefer a verified real witness or explicitly use a non-witness grammar fragment without `~ 1 1 1`.

### Our issue 3: `src/verify.cpp` does not perform the checks promised by its comments

The comments at `src/verify.cpp:9` claim legal-grid geometry and halo coverage checks. The implementation at `src/verify.cpp:27` only:

- materializes placements and rejects occupied-cell collisions; and
- asks `HoleFinder` whether the union contains holes.

It does not check:

- legal symmetry-group membership;
- lattice-valid translation;
- exactly one central tile;
- submitted versus recomputed levels;
- orphan/disconnected copies;
- contact with the preceding level; or
- complete boundary/halo coverage.

A hole-free cluster is not necessarily a corona witness. Layr Labs' `patch.py` is the better reference implementation for this component.

### Our issue 4: the final script recomputes the shape rather than validating the submitted arrangement

`AI_challenge/run_ai_validate.sh:64` first runs the weak `verify` helper. It then invokes `sat` without `-update` at `AI_challenge/run_ai_validate.sh:73`. The C++ path at `src/sat.cpp:31` constructs a new `HeeschSolver` from the base shape and overwrites its classification.

Therefore the final `YES` depends mainly on the newly generated SAT result, not on whether the AI's arrangement was a correct witness. This can be a reasonable **shape-classification** workflow, but it does not implement the stated challenge “submit the whole arrangement and we validate that arrangement.”

The contract must choose one of two models:

1. **Witness challenge:** independently validate the exact submitted patch; or
2. **Shape challenge:** accept only shape geometry and let the server construct its own witness.

At present the prompt asks for model 1 while the decisive computation behaves like model 2.

### Our issue 5: the mathematical specification incorrectly calls graph distance equivalent to surrounding

`Submission_package/docs/challenge_spec.tex:13` says that a complete surround is equivalent to tile-adjacency graph distance. Graph-distance labels are necessary for corona indexing, but not sufficient: a sparse chain of tiles can have the correct graph distances while leaving most of the inner boundary exposed.

A correct condition needs both:

- recomputed level/distance constraints; and
- full boundary or halo coverage by each next level.

### Our issue 6: our record rationale conflates two shape classes

Our prompt asks for `Hc >= 7` and the validator comment says this is one more than the documented record 6 (`AI_challenge/run_ai_validate.sh:34`). The record 6 concerns a more general planar figure, not an unmarked `O/H/I` polyform. For the unmarked polyform class implemented by the challenge, the cited computational record is 4.

Both targets can be meaningful, but they mean different things:

| Target | Correct interpretation |
|---|---|
| `Hc >= 5` | First known unmarked `O/H/I` polyform exceeding Kaplan's class record 4 |
| `Hc >= 7` | A much stronger stretch target that would also exceed the known general finite record 6 |

Calling 7 the “clean next class record” is inaccurate. It is an intentionally extreme stretch target whose feasibility below 200 cells is unknown.

### Our issue 7: our explanation of a `YES` result is too weak in one place and too strong in another

`Submission_package/README.md:69` says `YES` only means that no isohedral tiling was found. In fact, the current decision also requires a finite `~ hc hh` classification from `sat`. When `sat` reaches an unsatisfiable next-corona instance, that computational result is evidence of a finite Heesch number and hence non-tiling under the trusted encoder/solver implementation.

Conversely, it is not a proof-carrying certificate: the package does not emit or independently check a DRAT/LRAT proof, and the C++ code itself records a known `-maxlevel` edge-case at `src/heesch.h:1004`. The accurate statement is:

> `YES` means the bundled C++ SAT implementation recomputed a finite `Hc` meeting the threshold and its generated patch passed the package's limited overlap/hole checks. This is a trusted-program computational result, not an independently checkable proof certificate, and it does not certify the AI-supplied patch as submitted.

## Record threshold: 5 versus 7

For a benchmark specifically restricted to unmarked polyominoes, polyhexes, and polyiamonds, the scientifically calibrated first record target is:

\[
H_c(S)\ge 5,
\]

provided non-tilerhood is also certified. This is the external repository's strongest conceptual choice and is better aligned with Kaplan's class-specific data than our current explanation for 7.

`Hc >= 7` remains a valid, much harder challenge. It should be described as exceeding the known general finite record 6, not merely as the next unmarked-polyform record. It may be useful as a long-horizon aspirational benchmark, but a verifier must still have a logically sound positive path.

## Recommended remediation

### Required before treating the external benchmark as a record verifier

1. **Split the boards.** Keep an explicitly named `finite-corona lower-bound` board on which tilers are allowed, and a separate `finite Heesch record` board.
2. **Fail closed for record promotion.** `INCONCLUSIVE` from the tiler gate must never be sufficient for the record board.
3. **Integrate the proof path.** Extend the submission contract with proof metadata, invoke `check_proof_v2`, require the reviewed multilevel epoch, and make `ProofCarryingGate` return a real enforced verdict.
4. **Publish the missing specifications.** The exact encoder and architecture documents must be part of the immutable release.
5. **Version the soundness theorem.** Remove the stale v1 exactness inference and state the v2 implication with all assumptions.
6. **Add census-regression tests at the first out-of-table sizes.** The three counts in this report are useful permanent tests of gate incompleteness and documentation accuracy.
7. **Correct public claims.** Replace “plane tilers are rejected” with the exact gate guarantee until the proof tier is live.

### Required before treating our package as a submitted-arrangement verifier

1. Correct the affine transform formula in every prompt, README, JupyterBook chapter, and example.
2. Replace the toy domino patch with a witness that passes an independent corona checker.
3. Port or reimplement the external transform, level, orphan, surround, and hole checks.
4. Decide whether the submitted patch or the server-recomputed patch is the actual challenge object.
5. If exact finite claims matter, emit solver proofs and validate them with an independent checker.
6. Reframe `Hc>=5` as the first unmarked-polyform record target and `Hc>=7` as the all-time-record stretch target.
7. Add adversarial regression cases for shears, wrong affine offsets, multiple centers, wrong levels, orphan tiles, uncovered halo cells, hidden holes, and tilers missed by the fast gate.
8. Add CI and make the Docker build reproducible by digest-pinning the base image and source dependency commits.

### Recommended combined architecture

```text
participant shape + witness
        |
        v
strict parser and resource bounds
        |
        v
independent geometry verifier  -----> proves Hc >= k
        |
        +----> fast constructive tiler filters
        |
        v
all-level CNF for corona k+1
        |
        +---- SAT  -> exactness undecided; lower bound only
        |
        +---- UNSAT + checked proof
                       |
                       v
              Hc = Hh = k and non-tiler
                       |
                       v
              eligible for record board
```

The original C++ `heesch-sat` run should then be retained as an independent cross-check and witness generator, not as the sole unverified trust root.

## Reproduction record

### External tests

```bash
git clone --depth 1 https://github.com/Layr-Labs/heesch-challenge.git
cd heesch-challenge
python3 -m venv .venv-review
.venv-review/bin/pip install -e '.[test]'
.venv-review/bin/pytest -q
```

Observed at commit `e50e6cad940431b21e055c3b575690cdf217bb92`:

```text
372 passed, 10 skipped in 95.61s
```

### Census-gate audit

After the editable install above, download the three authoritative `0up` files:

```bash
curl -fsSLo /tmp/09omino_0up.txt \
  https://cs.uwaterloo.ca/~csk/heesch/omino/09omino_0up.txt
curl -fsSLo /tmp/07hex_0up.txt \
  https://cs.uwaterloo.ca/~csk/heesch/hex/07hex_0up.txt
curl -fsSLo /tmp/10iamond_0up.txt \
  https://cs.uwaterloo.ca/~csk/heesch/iamond/10iamond_0up.txt
```

Run this from the external repository root:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "tools"))

import classify
from heesch_verify.canonical import canonical_digest
from heesch_verify.gates import IsohedralGate, Verdict
from heesch_verify.grids import GRIDS
from heesch_verify.shape import holes_of

cases = [
    ("O", 9, Path("/tmp/09omino_0up.txt")),
    ("H", 7, Path("/tmp/07hex_0up.txt")),
    ("I", 10, Path("/tmp/10iamond_0up.txt")),
]

for grid_id, size, path in cases:
    grid = GRIDS[grid_id]
    lines = path.read_text().splitlines()
    non_tilers = set()
    for line in lines[0::2]:
        values = list(map(int, line.split()))
        cells = list(zip(values[0::2], values[1::2]))
        non_tilers.add(canonical_digest(cells, grid, True))

    total = holed = tilers = caught = missed = 0
    for cells in classify.free_polyforms(grid_id, size):
        total += 1
        tile = frozenset(cells)
        if holes_of(tile, grid):
            holed += 1
            continue
        if canonical_digest(cells, grid, True) in non_tilers:
            continue
        tilers += 1
        verdict, _detail = IsohedralGate(grid).check_detailed(tile)
        if verdict is Verdict.TILER:
            caught += 1
        else:
            missed += 1

    print(
        grid_id, size, total, holed, len(non_tilers),
        tilers, caught, missed,
    )
```

Observed output, in columns `grid size free holed non-tilers tilers caught missed`:

```text
O 9 1285 37 198 1050 961 89
H 7 333 2 37 294 257 37
I 10 448 4 103 341 262 79
```

### Baseline harness

The committed baseline was accepted with:

```text
score = 1.0
hc_verified = 1
gate_tier = isohedral_inconclusive
gate_detail = evaluated:no_factorization
```

This is an example of the central policy issue: even the baseline is scored after an inconclusive, rather than non-tiler, gate verdict. The baseline shape is a known small non-tiler, but the executable rule does not establish that fact.

### Local smoke test status

The local package smoke command was attempted during this audit:

```bash
./Submission_package/scripts/run_smoke_tests.sh
```

It could not start because the local Docker daemon was unavailable at `/Users/airbartek/.docker/run/docker.sock`. This is an environment precondition failure, not evidence that the smoke assertions passed or failed. The source-level local findings above do not depend on Docker execution.

## Final assessment

### Layr Labs repository

**Research-witness verifier:** strong.  
**Hostile-input benchmark engineering:** strong.  
**Finite-record acceptance theorem:** not implemented by the enabled harness.  
**Exactness/non-tiler proof path:** promising but dormant, incomplete as a public contract, and still marked as externally unreviewed.

### Our repository

**Underlying Heesch SAT classifier:** stronger for computing a finite upper obstruction when it terminates.  
**Submitted-arrangement verification:** currently inadequate.  
**Participant-facing mathematical format:** contains a critical affine-transform error and an invalid toy witness.  
**Proof-carrying reproducibility:** absent.

### Deployment recommendation

Do not deploy either current package as a binary `YES = new finite Heesch record` oracle without qualification. The external verifier is the better foundation for validating supplied witness geometry; our C++ solver is the better existing component for independently searching all corona levels. A robust release should combine them and make the proof/non-tiler gate part of the same executable acceptance path.
