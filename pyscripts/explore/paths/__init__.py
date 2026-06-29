"""The three reasoning paths. Each module exposes NAME and run(snapshots, model)."""

from pyscripts.explore.paths import bugs, features, stories

REGISTRY = {p.NAME: p for p in (bugs, features, stories)}
