"""Discovery Engine — hypotheses, calibrated experiments and the evidence loop.

Recommendation → hypothesis → smallest next action → reflection → experience
evidence → recalibrated recommendations. Experiment design is deterministic
and explainable (calibrated to age/class, ability, working style); AI may only
polish wording and extract features from reflection text.
"""

from .calibration import ALL_MODALITIES, Calibration, calibrate
from .catalog import ActionTemplate, choose_action
from .engine import (
    ACCEPTED,
    COMPLETED,
    ENGINE_VERSION,
    EXPERIENCE_PREFIXES,
    PROPOSED,
    SKIPPED,
    DiscoveryEngine,
    Experiment,
    Reflection,
    evidence_strength,
)

__all__ = [
    "ACCEPTED",
    "ALL_MODALITIES",
    "ActionTemplate",
    "COMPLETED",
    "Calibration",
    "DiscoveryEngine",
    "ENGINE_VERSION",
    "EXPERIENCE_PREFIXES",
    "Experiment",
    "PROPOSED",
    "Reflection",
    "SKIPPED",
    "calibrate",
    "choose_action",
    "evidence_strength",
]
