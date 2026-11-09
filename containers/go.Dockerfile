# Builds are gated by docs/IMPLEMENTATION_PLAN.md; linux/amd64 only.
FROM docker.io/library/golang:1.26.8-bookworm@sha256:26de5cf8eac40c12a1ff8de1a634971b4654fd881225eed7ace643b8c769f2f5 AS builder
WORKDIR /src
ENV GOTOOLCHAIN=local GOMAXPROCS=1 CGO_ENABLED=0
COPY go.mod go.sum ./
RUN go mod download && go mod verify
# The Dockerfile-specific allowlist excludes eval, fixtures, artifacts and secrets.
COPY . .
RUN go build -p 1 -trimpath -o /out/mcp-gateway ./cmd/mcp-gateway && go build -p 1 -trimpath -o /out/agent ./cmd/agent && go build -p 1 -trimpath -o /out/billing-mcp ./cmd/billing-mcp
# Deterministic integration target is a separate explicitly identified image.
ARG MCPBENCH_SCRIPTED_SCENARIO=smoke
RUN go build -p 1 -trimpath -ldflags "-X main.scenario=${MCPBENCH_SCRIPTED_SCENARIO}" -o /out/scripted-agent ./tests/integration/scripted-agent

FROM docker.io/library/debian:bookworm-slim@sha256:c67e92c8099ba22853ab4cfda7cfb494d253d6012ca82dee98ba8976772af018 AS runtime
USER 1000:1000
WORKDIR /app
ENV HOME=/nonexistent TMPDIR=/tmp

FROM runtime AS agent
COPY --from=builder /out/agent /app/agent
ENTRYPOINT ["/app/agent"]

FROM runtime AS mcp
COPY --from=builder /out/billing-mcp /app/billing-mcp
ENTRYPOINT ["/app/billing-mcp"]

FROM runtime AS scripted-agent
COPY --from=builder /out/scripted-agent /app/agent
ENTRYPOINT ["/app/agent"]

FROM runtime AS gateway
COPY --from=builder /out/mcp-gateway /app/mcp-gateway
ENTRYPOINT ["/app/mcp-gateway"]
