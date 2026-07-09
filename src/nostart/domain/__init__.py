"""Domain package — ground-truth physics and scenario definitions."""

from nostart.domain.components import (
    Component,
    FailureMode,
    InjectedFault,
)
from nostart.domain.propagation import (
    VALID_NODES,
    CrankBehavior,
    EngineState,
    Node,
    SymptomState,
    resolve_symptoms,
)
from nostart.domain.scenarios import ScenarioDef, get_scenario, list_scenarios

__all__ = [
    "Component",
    "FailureMode",
    "InjectedFault",
    "CrankBehavior",
    "EngineState",
    "Node",
    "VALID_NODES",
    "SymptomState",
    "resolve_symptoms",
    "ScenarioDef",
    "get_scenario",
    "list_scenarios",
]
