"""Stage 5 — Confidence Estimation.

Estimates overall profile confidence in [0,1] from assessment completeness,
signal decisiveness (how far signals are from neutral), and the amount of
evidence. Missing data lowers confidence. Pure and deterministic.
"""

from __future__ import annotations

from ..assessment.responses import AssessmentResult
from .models import EvidenceItem, StudentSignals

# Weights for the confidence blend (tunable, named).
_W_COMPLETENESS = 0.4
_W_DECISIVENESS = 0.3
_W_EVIDENCE = 0.3
_EVIDENCE_SATURATION = 8  # evidence count at which the evidence factor maxes out


def estimate_confidence(
    assessment: AssessmentResult,
    signals: StudentSignals,
    evidence: tuple[EvidenceItem, ...],
) -> float:
    completeness = (
        assessment.quality.completion if assessment.quality is not None else 0.5
    )

    # Decisiveness: mean distance from the neutral midpoint (0.5), scaled to [0,1].
    pairs = signals.as_pairs()
    decisiveness = sum(abs(v - 0.5) * 2 for _, v in pairs) / len(pairs)

    evidence_factor = min(1.0, len(evidence) / _EVIDENCE_SATURATION)

    score = (
        _W_COMPLETENESS * completeness
        + _W_DECISIVENESS * decisiveness
        + _W_EVIDENCE * evidence_factor
    )
    return max(0.0, min(1.0, score))
