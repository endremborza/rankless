"""The snapshot reasoning paths. Each module exposes NAME and run(snapshots, model).

Agentic exploration over a live backend is a separate command
(`pyscripts.explore.deep`), not a path here.
"""

from pyscripts.explore.paths import bugs, features, stories

REGISTRY = {p.NAME: p for p in (bugs, features, stories)}
