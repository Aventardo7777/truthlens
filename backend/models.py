"""Core data models shared across the TruthLens analysis engine.

Design principle: every issue detected by the engine becomes a `Finding` --
a structured piece of *evidence*. Findings never assert fraud; they describe
what was observed, why it matters, what could explain it, and what it cannot
prove. TruthLens is a forensic tool, not a judge.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Severity & evidence levels
# ---------------------------------------------------------------------------
SEVERITY_LOW = "low"
SEVERITY_MODERATE = "moderate"
SEVERITY_HIGH = "high"

EVIDENCE_LOW = "low"
EVIDENCE_MODERATE = "moderate"
EVIDENCE_HIGH = "high"

# Layers of the forensic pipeline
LAYER_HEALTH = "data_health"          # Layer 1: basic data quality
LAYER_STATISTICAL = "statistical"     # Layer 2: statistical anomalies
LAYER_PATTERN = "pattern_forensics"   # Layer 3: pattern forensics
LAYER_BASELINE = "baseline"           # Synthetic baseline comparison


@dataclass
class Finding:
    """A single detected issue, phrased as forensic evidence."""

    id: str
    layer: str
    category: str
    title: str
    severity: str                       # low | moderate | high
    evidence_level: str                 # low | moderate | high
    stat_summary: str                   # human readable key numbers
    evidence: dict[str, Any] = field(default_factory=dict)
    why_it_matters: str = ""
    possible_causes: list[str] = field(default_factory=list)
    what_it_does_not_prove: str = ""
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def score_penalty(self) -> float:
        """How strongly this finding drags down the integrity score."""
        base = {SEVERITY_LOW: 1.0, SEVERITY_MODERATE: 2.5, SEVERITY_HIGH: 4.5}
        return base.get(self.severity, 1.0)


@dataclass
class ColumnProfile:
    """Per-column summary used by the dashboard."""

    name: str
    dtype: str
    role: str                            # numeric | categorical | datetime | text | constant
    count: int
    missing: int
    missing_pct: float
    unique: int
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntegrityScore:
    """Composite trustworthiness assessment."""

    total: int                           # 0..100
    verdict: str                         # e.g. "Moderate Integrity"
    dimensions: dict[str, int] = field(default_factory=dict)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    """The complete forensic scan output for one dataset."""

    scan_id: str
    case_number: str
    filename: str
    created_at: str
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    integrity: Optional[IntegrityScore] = None
    correlation_network: dict[str, Any] = field(default_factory=dict)
    charts: dict[str, Any] = field(default_factory=dict)
    synthetic_comparison: dict[str, Any] = field(default_factory=dict)
    fingerprint: dict[str, Any] = field(default_factory=dict)
    pipeline_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def findings_by_layer(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.layer, []).append(f)
        return out


def verdict_for(score: int) -> str:
    if score >= 85:
        return "High Integrity"
    if score >= 70:
        return "Moderate Integrity"
    if score >= 50:
        return "Questionable Integrity"
    return "Low Integrity"
