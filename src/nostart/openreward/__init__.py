"""OpenReward (ORS) adapter — serves the environment unchanged over ORS.

See docs/openreward_integration.md for the spec mapping and design decisions.
"""

from nostart.openreward.env import NoStartEnv

__all__ = ["NoStartEnv"]
