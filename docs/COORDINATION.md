# Eigen / Yukon coordination checklist

Everything Yukon-side that has to happen before and at import. Mirrors the
process used for TNCOO and the author guide's private-repo path.

- [ ] Create private repo under `Layr-Labs/` (private is required so
      submission PRs are not world-readable mid-competition).
- [ ] Push this challenge repo (default branch = the branch Yukon imports).
- [ ] Install the Yukon GitHub App on the repo:
      - Dev: https://github.com/apps/yukon-eigen/installations/new
      - Prod: https://github.com/apps/yukon-autoresearch/installations/new
- [ ] Invite solvers / org as read collaborators (needed for `yukon clone`;
      Yukon does not mint clone tokens).
- [ ] Verify `benchmark.json` final: name, description, direction,
      `minScoreImprovementBips`, `maxSubmissionBytes`.
- [ ] Verify workflow runs green on `workflow_dispatch` and uploads
      `.yukon/score.json` as an artifact (≤ 50 MiB).
- [ ] Contact Yukon team for import; they queue the baseline run and wire
      CLI, database, and frontend.
- [ ] Never merge submission PRs manually — promotion is Yukon's
      fast-forward of the scored commit.
