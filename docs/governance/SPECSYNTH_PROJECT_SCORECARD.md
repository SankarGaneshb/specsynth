# Specsynth Project Scorecard

**Snapshot date:** 2026-11-28  
**Repository:** [SankarGaneshb/specsynth](https://github.com/SankarGaneshb/specsynth)  
**Reviewed implementation baseline:** `99af4f2d121b4e512ec9ffbe62574eb707a4c9fa`  
**Status:** Initial qualitative baseline — not a certification or a percentage-complete claim.

> Specsynth is the scientific framework. PerandamΨ is its integrated interactive research environment, not a separate product. The PerandamΨ Cosmic Galaxy Challenge is a separate programme and is not included in this scorecard.

## 1. Why this scorecard exists

This scorecard reports project progress without confusing implementation with scientific trust. Every dimension has two independent assessments:

1. **Delivery status:** how much of the agreed capability is present.
2. **Evidence maturity:** what has actually been demonstrated, and how strong that evidence is.

A passing software test does not by itself establish astrophysical validity. A provenance manifest does not by itself establish that the underlying scientific data or interpretation is correct. No overall weighted score is published: a high aggregate could conceal a critical scientific weakness.

## 2. Delivery status vocabulary

| Status | Meaning |
|---|---|
| Not started | No material implementation identified |
| Designed | Requirements or design exist; implementation not demonstrated |
| In progress | Some implementation exists; agreed scope is incomplete |
| Implemented | Capability exists in code or the product; this does not imply adequate testing |
| Tested | Relevant automated/integration tests have been demonstrated for the stated scope |
| Validated | Results have been compared with suitable independent scientific evidence for a clearly bounded claim |
| Independently reviewed | A qualified reviewer outside the implementation team has examined the specified evidence |
| Blocked | Progress depends on an external decision, access, asset or unresolved prerequisite |
| Unknown | Evidence is insufficient to assign a reliable status |

Statuses are not interchangeable. In particular, **Implemented**, **Tested**, **Validated** and **Independently reviewed** must never be used as synonyms.

## 3. Evidence maturity levels

| Level | Name | Minimum evidence |
|---|---|---|
| E0 | Not assessed | No relevant evidence collected |
| E1 | Specified | Requirement, scientific claim, acceptance criteria and limitations documented |
| E2 | Implemented | Identifiable implementation exists at a recorded commit |
| E3 | Behaviourally tested | Relevant tests exercise the behaviour; results, failures and skips are recorded against the exact commit |
| E4 | Independently validated | A suitable independent reference, dataset, method or qualified external review supports the bounded claim |

E4 is claim-specific. A numerical comparison may validate one equation or parameter domain, not an entire scientific engine. External review is recorded separately from automated test status.

## 4. Initial dimension scorecard

This is a cautious qualitative baseline based on the repository evidence and review available on 2026-11-28. It is not a claim that every file, workflow or scientific output has been independently re-executed. Where the evidence is incomplete, the status is deliberately conservative.

| # | Dimension | Delivery status | Evidence maturity | Achievements identified | Pending / next evidence |
|---:|---|---|---|---|---|
| 1 | Architecture, scope and contracts | Implemented | E2–E3 | Frozen north-star and architecture governance exist; adapter-first integration boundary is defined. | Keep code, roadmap and reviewer documentation aligned; verify conformance continuously. |
| 2 | Core scientific engine and Python API | Implemented | E2–E3 | Core synthesis and scientific APIs are present with automated tests. | Build a claim-to-reference validation matrix covering supported domains, assumptions and numerical tolerances. |
| 3 | Cosmology and physical calculations | Implemented | E3 for bounded claims | Automated checks cover selected cosmology and physical invariants. | Expand independent reference comparisons and parameter/domain coverage; document exclusions. |
| 4 | Stellar population and spectral synthesis | In progress | E2–E3 | SSP/spectral synthesis pathways and adapter interfaces exist. | Demonstrate against independently maintained scientific engines and suitable reference spectra, including uncertainty and configuration matching. |
| 5 | External engine integration | In progress | E2 | Adapter/conformance examples and an external-plugin demonstration exist. | Complete an end-to-end integration with an independently maintained engine without modifying the Specsynth core. |
| 6 | 3D galaxy modelling and source assets | In progress | E2–E3; authenticity not certified here | 3D contracts, rendering path and source-asset verification code are present. | Independently verify the actual asset bytes, trusted manifest, embedded metadata, data access terms and scientific interpretation. |
| 7 | Cosmic-time and galaxy evolution | In progress | E2–E3 | Evolution/merger-tree workflows and structural checks exist. | Validate source lineage, physical assumptions, mass accounting and derived quantities against independent references; document tolerances and limitations. |
| 8 | Source provenance and execution provenance | In progress | E2–E3; open review gate | Separate source and execution provenance contracts and Issue #33 remediation are present in the latest implementation commit. | Close Issue #33 only after trusted-manifest verification, fail-closed behaviour, actual UI lifecycle tests and Python/Node/API/export parity are demonstrated. |
| 9 | Reproducibility and lineage | In progress | E2 | Provenance structures and reproducibility-oriented workflows are present. | Demonstrate clean-environment reproduction from immutable inputs through parameters, software versions, outputs and exports. |
| 10 | Python MCP interoperability | Implemented | E2–E3 | Python MCP server and canonical tool contracts exist. | Verify actual transport-level behaviour, error semantics, schema compatibility and reproducibility for supported workflows. |
| 11 | Node.js MCP and cross-runtime parity | In progress | E2–E3 | Node server and parity tests exist. | Compare complete normalized positive and negative response fixtures across runtimes; add transport-level acceptance evidence. |
| 12 | PerandamΨ integrated research environment | Implemented | E2–E3; scientific display trust remains gated | Interactive exploration, visualisation and provenance/execution UI components exist. | Verify every displayed result against its current input, source lineage and actual execution path using browser-level tests. |
| 13 | Documentation and reviewer readiness | In progress | E1–E2 | Governance and reviewer-readiness documentation exist. | Reconcile claims and evidence to the exact reviewed commit; label reported, reproduced, skipped and independently validated results distinctly. |
| 14 | Independent scientific review | Not started / not established | E0–E1 | Review questions and a claim-to-evidence approach have been identified. | Obtain qualified external review of a small, well-defined set of scientific workflows and publish scope, findings and limitations. |

**Interpretation:** The project has a substantial software foundation and working product components. Its overall scientific-readiness claim remains unestablished until the critical provenance, numerical-validation, reproducibility and independent-review evidence is complete.

## 5. Scientific trust release gates

These gates are release controls, not an averaged score. A release cannot claim scientific readiness while a required gate is open.

| Gate | Requirement | Evidence required | Initial status |
|---|---|---|---|
| G1 — Data authenticity | Inputs are correctly identified and their provenance claims are justified. | Trusted source manifests, byte-level integrity checks where applicable, metadata validation, licensing/access records and explicit unknown states. | Open — do not treat repository assertions as independent certification. |
| G2 — Scientific correctness | Bounded calculations agree with accepted independent methods/data within documented tolerances. | Reference comparisons, dimensional/unit checks, physical invariants, domain limits, uncertainty and failure analysis. | Partial — selected tests exist; comprehensive independent validation is not established. |
| G3 — Reproducibility | A reviewer can reproduce a result from recorded inputs and configuration. | Immutable input identity, parameters, code/dependency versions, execution record, deterministic or characterised stochastic behaviour, and repeat-run comparison. | Partial — end-to-end evidence still required. |
| G4 — Interface integrity | UI, Python, Node MCP, API and exports report the same result semantics and provenance. | Behavioural, browser E2E, transport and cross-runtime parity tests, including failure and stale-response cases. | Open — Issue #33 remains a review gate. |
| G5 — Independent review | Qualified people outside the implementation team review bounded scientific claims. | Reviewer identity/qualification, scope, evidence package, findings and resolution record. | Not established. |
| G6 — Release readiness | All release claims are supported and limitations are visible. | G1–G5 disposition, known-issues register, reproducible test report, versioned documentation and sign-off. | Not ready to claim scientific validation. |

## 6. Operational metrics to report each snapshot

Report counts with their denominator and scope. Never report a percentage if the denominator is unknown or unstable.

### Delivery
- Requirements completed / total approved requirements, by milestone and priority.
- Issues open, closed and blocked, grouped by P0/P1/P2 and milestone.
- Acceptance criteria evidenced / total acceptance criteria, by issue.
- Capabilities implemented / planned, only where the inventory is controlled and non-duplicative.

### Engineering quality
- CI runs for the exact commit: passed, failed, cancelled and skipped.
- Test counts by unit, integration, browser E2E, transport and parity category.
- Coverage metrics only with the measured scope and tool/configuration stated.
- Regressions, open defects and time-to-resolution.

### Scientific trust
- Source records by verification state: verified, declared, unknown and invalid.
- Scientific claims with E0–E4 evidence, grouped by domain and supported parameter range.
- Independent reference comparisons completed / planned, with tolerance and reference identity.
- Reproducibility workflows passed / attempted, including clean-environment reruns.
- Open scientific limitations, unresolved assumptions and known failure modes.

### Interoperability and research environment
- Canonical MCP tools tested in Python and Node / total canonical tools.
- Complete parity fixtures passed / total fixtures, including invalid and missing-data cases.
- UI result paths tested / total interactive scientific result paths.
- Export formats preserving provenance / total supported export formats.

### Independent assurance
- Claims reviewed by an external qualified reviewer / claims selected for review.
- Findings open, resolved and accepted with documented rationale.
- Release gates passed / required gates, with no averaging across gates.

## 7. Rules for calculating and publishing percentages

1. Establish a version-controlled inventory of requirements before calculating implementation completion.
2. Count each requirement once; define whether partial completion is allowed and how it is evidenced.
3. Publish implementation completion separately from evidence maturity.
4. Do not assign E4 from unit tests, source-code inspection, a self-authored report or a provenance label alone.
5. Show skipped tests separately; never count them as passed.
6. Bind every test report and scorecard snapshot to a commit SHA, workflow run and environment.
7. Preserve historical snapshots so progress and regressions are visible.
8. Do not calculate one overall weighted score or allow high engineering completion to compensate for an open scientific trust gate.
9. Mark unavailable metrics as **Not measured**, not zero and not complete.
10. Record who reviewed each scientific claim and the exact scope of the conclusion.

## 8. Update cadence and ownership

- **On every significant merge:** refresh commit-linked engineering evidence and affected acceptance criteria.
- **At each milestone review:** reconcile all 14 dimensions, open blockers and trust gates.
- **At release candidates:** perform a full G1–G6 review and freeze the evidence package.
- **Ownership:** engineering metrics may be generated automatically; scientific validation states require a named reviewer and traceable evidence.
- **Change history:** append dated snapshots or link immutable CI-generated reports; do not silently rewrite historical results.

## 9. Immediate priorities for the next baseline

1. Resolve the open scientific provenance and truthful execution review in [Issue #33](https://github.com/SankarGaneshb/specsynth/issues/33).
2. Reconcile the reviewer-readiness document to the exact reviewed commit and downgrade any claim whose evidence does not meet its stated verification definition.
3. Create a controlled requirements/claim inventory for the 14 dimensions so future completion ratios have defensible denominators.
4. Define a small independent scientific validation suite: one spectral-synthesis workflow, one cosmology/physical calculation, one 3D source-data workflow and one evolution workflow.
5. Arrange an external astrophysicist review of that bounded evidence package.

## 10. Snapshot disclaimer

This document is a project-management and evidence-governance instrument. Its qualitative statuses are an initial reviewer assessment, not an exhaustive audit, scientific certification, endorsement of every repository claim or guarantee of correctness. Update each row only when new, traceable evidence supports the change.
