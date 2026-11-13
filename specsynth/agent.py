from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from specsynth.tools import (
    tool_clean_catalog,
    tool_get_system_info,
    tool_inspect_anomaly,
    tool_inspect_galaxy,
    tool_run_sentry_audit,
)


@dataclass
class RootCauseCluster:
    """Grouped analysis of anomalies sharing a common failure mode."""
    category: str
    metric_name: str
    count: int
    sample_galaxy_indices: list[int]
    observed_range: tuple[float, float]
    primary_hypothesis: str
    recommended_action: str
    affected_parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInvestigationResult:
    """Complete structured output from an autonomous SentryAgent investigation."""
    timestamp: str
    base: str
    status: str  # CERTIFIED_PRISTINE, REMEDIATED_CLEAN, CRITICAL_REJECTED
    total_evaluated: int
    passed_count: int
    flagged_count: int
    pass_rate_pct: float
    retention_rate_pct: float | None = None
    clusters: list[RootCauseCluster] = field(default_factory=list)
    quarantined_indices: list[int] = field(default_factory=list)
    clean_catalog_path: str | None = None
    memo_path: str | None = None
    host_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path, indent: int = 2) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=indent)


class SentryAgent:
    """
    Autonomous Scientific Quality Assurance & Remediation Agent for Specsynth.

    Executes a multi-stage reasoning loop:
      1. Audit: Evaluates catalog through 4-tier diagnostic invariants.
      2. Investigate: Diagnoses root causes by correlating faults with galaxy input parameters.
      3. Remediate: Automatically purges corruptions to produce a verified clean catalog.
      4. Synthesize: Authors an executive scientific memo certifying catalog readiness.
    """

    def __init__(
        self,
        base: str = "./run",
        sample_size: int = 50_000,
        max_anomaly_rate: float = 0.001,
        auto_remediate: bool = True,
        raw_catalog_path: str | None = None,
        clean_output_path: str = "clean_catalog.parquet",
        output_memo_path: str = "sentry_agent_memo.md",
    ):
        self.base = str(base)
        self.sample_size = int(sample_size)
        self.max_anomaly_rate = float(max_anomaly_rate)
        self.auto_remediate = bool(auto_remediate)
        self.raw_catalog_path = raw_catalog_path
        self.clean_output_path = clean_output_path
        self.output_memo_path = output_memo_path

    def run(self) -> AgentInvestigationResult:
        """Execute the full autonomous investigation and remediation loop."""
        now_iso = datetime.now(timezone.utc).isoformat()
        host_info = tool_get_system_info()

        # Step 1: Run Diagnostic Audit
        audit_res = tool_run_sentry_audit(
            base=self.base,
            sample_size=self.sample_size,
        )

        total_eval = audit_res.get("total_galaxies_evaluated", 0)
        passed_cnt = audit_res.get("passed_count", 0)
        flagged_cnt = audit_res.get("flagged_count", 0)
        pass_rate = audit_res.get("pass_rate_pct", 100.0)
        anomalies = audit_res.get("anomalies", [])

        # Step 2: Root-Cause Investigation & Clustering
        clusters, quarantined_indices = self._investigate_anomalies(anomalies)

        # Step 3: Autonomous Remediation (if requested and anomalies exist)
        clean_path = None
        retention_rate = None

        if flagged_cnt == 0:
            status = "CERTIFIED_PRISTINE"
            retention_rate = 100.0
        elif self.auto_remediate and quarantined_indices:
            clean_res = tool_clean_catalog(
                base=self.base,
                output_path=self.clean_output_path,
                source_table_path=self.raw_catalog_path,
            )
            clean_path = str(self.clean_output_path)
            retention_rate = clean_res.get("retention_rate_pct", pass_rate)
            status = "REMEDIATED_CLEAN" if pass_rate >= (1.0 - self.max_anomaly_rate) * 100.0 else "CRITICAL_REJECTED"
        else:
            status = "INVESTIGATION_FLAGGED"

        result = AgentInvestigationResult(
            timestamp=now_iso,
            base=self.base,
            status=status,
            total_evaluated=total_eval,
            passed_count=passed_cnt,
            flagged_count=flagged_cnt,
            pass_rate_pct=pass_rate,
            retention_rate_pct=retention_rate,
            clusters=clusters,
            quarantined_indices=quarantined_indices,
            clean_catalog_path=clean_path,
            memo_path=self.output_memo_path,
            host_info=host_info,
        )

        # Step 4: Synthesize Publication-Ready Scientific Memo
        self._write_scientific_memo(result, audit_res)

        return result

    def _investigate_anomalies(
        self, anomalies: list[dict[str, Any]]
    ) -> tuple[list[RootCauseCluster], list[int]]:
        """Cluster anomalies by failure mode and correlate with galaxy input parameters."""
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        quarantined_set: set[int] = set()

        for a in anomalies:
            cat = a.get("category", "UNKNOWN")
            metric = a.get("metric_name", "unknown")
            g_idx = a.get("galaxy_index")
            if g_idx is not None:
                quarantined_set.add(int(g_idx))
            grouped.setdefault((cat, metric), []).append(a)

        clusters: list[RootCauseCluster] = []

        for (cat, metric), anom_list in grouped.items():
            vals = [
                float(a["observed_value"])
                for a in anom_list
                if a.get("observed_value") is not None and not isinstance(a["observed_value"], str)
            ]
            obs_range = (min(vals), max(vals)) if vals else (0.0, 0.0)
            sample_indices = [int(a["galaxy_index"]) for a in anom_list[:5] if a.get("galaxy_index") is not None]

            # Correlate first sample galaxy with its full parameter set
            correlated_params: dict[str, Any] = {}
            if sample_indices:
                try:
                    gal_details = tool_inspect_galaxy(base=self.base, galaxy_idx=sample_indices[0])
                    for k in ("tau_diffuse", "tau_birth", "total_stellar_mass_msun", "redshift"):
                        if k in gal_details:
                            correlated_params[k] = gal_details[k]
                except Exception:
                    pass

            hypothesis, action = self._deduce_hypothesis(cat, metric, correlated_params, anom_list[0])

            clusters.append(
                RootCauseCluster(
                    category=cat,
                    metric_name=metric,
                    count=len(anom_list),
                    sample_galaxy_indices=sample_indices,
                    observed_range=obs_range,
                    primary_hypothesis=hypothesis,
                    recommended_action=action,
                    affected_parameters=correlated_params,
                )
            )

        return clusters, sorted(quarantined_set)

    def _deduce_hypothesis(
        self, category: str, metric: str, params: dict[str, Any], sample_anom: dict[str, Any]
    ) -> tuple[str, str]:
        """Apply astrophysical and numerical deduction rules to pinpoint root causes."""
        if category == "INPUT_SCHEMA_FAULT":
            if "tau" in metric:
                return (
                    "Upstream catalog contains negative dust optical depths (tau < 0), causing unphysical energy generation.",
                    "Verify dust attenuation model in catalog generator and apply non-negative clipping tau = np.maximum(tau, 0.0).",
                )
            return (
                f"Input parameter violating schema contract on {metric}.",
                "Inspect upstream table column types and ranges prior to ingestion.",
            )

        if category == "NUMERICAL_FAULT":
            if metric == "finite_flux":
                return (
                    "Extreme attenuation or float32 exponent underflow produced NaN or Inf fluxes during matrix contraction.",
                    "Enforce a numerical flux floor (1e-35) or inspect SFH mass normalization.",
                )
            if metric == "energy_conservation":
                return (
                    "Attenuated flux exceeds intrinsic stellar flux (L_att > L_intr), violating 1st law of thermodynamics.",
                    "Ensure dust attenuation curves obey k(lambda) >= 0 everywhere.",
                )

        if category == "PHYSICAL_ANOMALY":
            if metric == "d4000_break":
                return (
                    "Inverted 4000Å break (D_n4000 < 0.95), indicating an impossible stellar atmosphere flux distribution.",
                    "Check for extreme unattenuated young burst components or inverted SFH time grids.",
                )
            if metric == "uv_slope_beta":
                return (
                    "UV continuum slope beta deviates from plausible stellar population limits ([-2.8, 1.5]).",
                    "Inspect massive star contributions and high-redshift IGM absorption settings.",
                )
            if metric == "ab_magnitude_range":
                return (
                    "Projected photometry falls outside astronomical survey limits (10 <= m <= 35).",
                    "Check galaxy luminosity distance scaling and photometric zeropoint calibrations.",
                )

        if category == "POPULATION_DRIFT":
            return (
                "Statistical population collapse detected: galaxy colors have zero dispersion, indicating degenerate parameters.",
                "Verify random parameter seeds and catalog column variability.",
            )

        return (
            sample_anom.get("root_cause", "Unclassified anomalous behavior observed during synthesis."),
            sample_anom.get("remediation", "Quarantine affected records and inspect simulation logs."),
        )

    def _write_scientific_memo(self, res: AgentInvestigationResult, audit_res: dict[str, Any]) -> None:
        """Write an executive Markdown & LaTeX quality assurance memo."""
        memo_path = Path(self.output_memo_path)
        memo_path.parent.mkdir(parents=True, exist_ok=True)

        status_badge = {
            "CERTIFIED_PRISTINE": "🟢 **CERTIFIED PRISTINE** (Ready for Science / Publication)",
            "REMEDIATED_CLEAN": "🟡 **REMEDIATED CLEAN** (Anomalies Quarantined & Filtered)",
            "CRITICAL_REJECTED": "🔴 **CRITICAL REJECTED** (Excessive Anomaly Rate Exceeded)",
            "INVESTIGATION_FLAGGED": "🟠 **INVESTIGATION FLAGGED** (Anomalies Require Review)",
        }.get(res.status, res.status)

        lines: list[str] = [
            "# Scientific Sentry Agent — Quality Assurance & Remediation Memo",
            "",
            f"**Audit Timestamp:** `{res.timestamp}`  ",
            f"**Data Store:** `{res.base}`  ",
            f"**Host Platform:** `{res.host_info.get('os', 'Unknown')}` (`{res.host_info.get('cpu_processor', 'CPU')}`, {res.host_info.get('total_ram_gb', 'N/A')} GB RAM)  ",
            f"**Evaluation Status:** {status_badge}  ",
            "",
            "---",
            "",
            "## 1. Executive Summary & Quality Certification",
            "",
            f"- **Total Galaxies Evaluated:** {res.total_evaluated:,}",
            f"- **Nominal / Valid Galaxies:** {res.passed_count:,} ({res.pass_rate_pct:.3f}%)",
            f"- **Anomalous / Quarantined:** {res.flagged_count:,}",
            f"- **Dataset Retention Rate:** {res.retention_rate_pct:.3f}%" if res.retention_rate_pct is not None else "",
            f"- **Clean Dataset Path:** `{res.clean_catalog_path}`" if res.clean_catalog_path else "- **Clean Dataset Path:** N/A (Original catalog is 100% clean)",
            "",
            "### Certification Statement",
        ]

        if res.status == "CERTIFIED_PRISTINE":
            lines.extend([
                "> **Scientific Readiness:** The synthesized catalog strictly satisfies all physical conservation laws, ",
                "> spectral continuum bounds ($D_n(4000)$, $\\beta_{\\text{UV}}$), and numerical precision gates with zero flagged anomalies. ",
                "> This catalog is certified ready for cosmological and astrophysical analysis.",
            ])
        elif res.status == "REMEDIATED_CLEAN":
            lines.extend([
                "> **Scientific Readiness:** Isolated numerical/physical anomalies were detected and safely quarantined. ",
                f"> An autonomous clean catalog was synthesized at `{res.clean_catalog_path}` with a **{res.retention_rate_pct:.2f}% retention rate**. ",
                "> The resulting sanitized dataset is safe for downstream scientific pipelines.",
            ])
        else:
            lines.extend([
                "> **Scientific Readiness:** The catalog contains unphysical anomalies exceeding safe operating margins. ",
                "> Upstream catalog generation must be reviewed before deploying into production.",
            ])

        lines.extend([
            "",
            "---",
            "",
            "## 2. Root-Cause Investigation & Anomaly Clusters",
            "",
        ])

        if not res.clusters:
            lines.append("No anomalous clusters were detected across any of the 4 diagnostic tiers.")
        else:
            lines.extend([
                "| Category | Diagnostic Metric | Affected Count | Observed Range | Sample Galaxy IDs |",
                "| :--- | :--- | :---: | :---: | :--- |",
            ])
            for c in res.clusters:
                samples = ", ".join(f"#{idx}" for idx in c.sample_galaxy_indices)
                lines.append(
                    f"| `{c.category}` | `{c.metric_name}` | {c.count:,} | `[{c.observed_range[0]:.2e}, {c.observed_range[1]:.2e}]` | {samples} |"
                )

            lines.extend(["", "### Detailed Root-Cause Analyses"])
            for idx, c in enumerate(res.clusters, 1):
                lines.extend([
                    f"#### Case #{idx}: `{c.category}` / `{c.metric_name}`",
                    f"- **Hypothesis:** {c.primary_hypothesis}",
                    f"- **Recommended Remediation:** {c.recommended_action}",
                ])
                if c.affected_parameters:
                    lines.append(f"- **Sample Parameter Context:** `{json.dumps(c.affected_parameters)}`")
                lines.append("")

        lines.extend([
            "---",
            "",
            "## 3. Invariants & Physics Gates Evaluated",
            "",
            "1. **Numerical Schema & Non-Negativity**: $\\forall \\lambda, F_\\lambda > 0$ and $F_\\lambda \\in \\mathbb{R}_{<\\infty}$.",
            "2. **Energy Conservation**: $\\int F_{\\text{att}}(\\lambda) d\\lambda \\le (1 + 10^{-6}) \\int F_{\\text{intr}}(\\lambda) d\\lambda$.",
            "3. **Stellar Atmospheric Invariants**: $D_n(4000) \\in [0.95, 2.50]$ and $\\beta_{\\text{UV}} \\in [-2.80, +1.50]$ (rest-frame).",
            "4. **Photometric Survey Bounds**: $10.0 \\le m_{\\text{AB}} \\le 35.0$ apparent magnitudes.",
            "5. **Statistical Population Dispersion**: Multi-color bimodality variance $\\sigma^2 > 10^{-4}$.",
            "",
            "---",
            "",
            "*Report autonomously compiled by Specsynth Scientific Sentry Agent.*",
        ])

        memo_path.write_text("\n".join(lines), encoding="utf-8")
