# Reproduction Plan

In this directory, we are trying to reproduce the rankless Rust backend with python and SQL tools, to create benchmarks for testing.

the relevant files:

- `repro-prompt.md`: the initial specification of the problem
- `schema.sql`: the schema of the postgres backend for reference
- `server.py`: the flask server that houses the python part of the reproduction
- `views.sql`: the sql views that extend the postgres schema to aid the flask server - these should be made in a way that they can be (attempted) to be added whenever the flask server starts up.
- `comp-eval.py`: evaluates the alignment of the 2 backends with a small set of test cases
- `create-schema-load-db.py`: creates the schema and loads the data into a backend postgres database that is then used for reproduction
- `schemas.yaml`: a manually edited file used in the previous file for schema creation

when iterating on the problem, the flask server from `server.py` is running in debug mode, so file changes restart it, and postres is available with the data loaded into it.
