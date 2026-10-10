"""mudmut_core — the in-process engine shared by the Streamlit UI, the CLI and the tests.

One library, used by the launcher, a headless CLI and the unit tests, so the
MUD (design) and MUT (unit-test) logic lives in exactly one place.
"""

__version__ = "0.1.0"

from mudmut_core import env  # noqa: F401  (ensure_environment on import)
