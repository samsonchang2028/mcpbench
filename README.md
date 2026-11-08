# MCPBench

Benchmarking MCP tool retrieval with a Go MCP service/agent, a separate Python
evaluator, PostgreSQL, and native Ollama/Qwen. The first runtime milestone is one
synthetic draft invoice with full-context tool exposure. Later comparisons remain
subject to the [task DAG](docs/TASK_GRAPH.md).

The repository currently contains frozen contracts, synthetic development fixtures,
and a dependency-pinned scaffold. Go agent/server and Python evaluator entrypoints
exit with code 2 and a bounded stderr message for every invocation. They perform
no runtime work and produce no result artifacts.

Read [project context](docs/PROJECT_CONTEXT.md), [architecture](docs/ARCHITECTURE.md),
[admission and stop rules](docs/IMPLEMENTATION_PLAN.md), and the [host audit](docs/NODE1_AUDIT.md).
Fresh resource/connectivity admission is required before dependency downloads or
compilation. Container startup and live inference have separate DAG gates.

With installed Go 1.26.8, CPython 3.14.4, and uv 0.13.4, from this repository root:

```sh
# Only after fresh admission; downloads packages into caches and a local .venv.
make setup
# Sequential dependency verification, Go compile/vet, 46 static tests and fixture CLI.
make check
```

`PYTHON=/absolute/path/to/python3.14 make setup check` selects an existing interpreter.
No interpreter, Go toolchain, or source-built Python dependency is downloaded.
See [dependency selections and evidence](docs/DEPENDENCIES.md) and
[image pins](config/images.lock.json). These commands do not start containers,
connect to PostgreSQL/MCP/Ollama, or execute live model tests.

`cmd/` and `internal/` reserve Go boundaries. `eval/` owns Python fixtures, grading,
reset, and lifecycle orchestration; `db/` reserves migrations/seeds, and
`observability/` reserves JSONL instrumentation. Existing contract and fixture
validation commands remain documented in [contracts](contracts/README.md) and
[fixtures](eval/fixtures/README.md). Only synthetic data is permitted.
