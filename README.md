# MCPBench

Benchmarking MCP tool retrieval: full context, semantic top-k, hybrid and
hierarchical retrieval. Initial scope is one synthetic draft invoice using a Go
MCP server, PostgreSQL and native Ollama/Qwen.

This is a planning scaffold, with no application or Compose implementation yet.
Start with [project context](docs/PROJECT_CONTEXT.md), the [Node 1 audit](docs/NODE1_AUDIT.md),
and the [implementation plan](docs/IMPLEMENTATION_PLAN.md). Architecture and
evaluation details are linked from the project context.

Git is initialized normally; host access was rechecked in [the audit](docs/NODE1_AUDIT.md).
The service-account model-storage target and full admission remain unresolved.
No services or native Ollama configuration have been changed.
