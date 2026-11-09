// Command billing-mcp serves only the synthetic billing MCP endpoint.
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"time"

	"mcpbench/internal/billing"
	"mcpbench/internal/mcp"
	"mcpbench/internal/store"
)

func main() {
	if len(os.Args) > 1 {
		fmt.Fprintln(os.Stderr, "mcpbench: invalid service arguments")
		os.Exit(2)
	}
	source, err := mcp.ServiceSource()
	if err != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: invalid service configuration")
		os.Exit(2)
	}
	// Trace factories and private unknown-outcome evidence must be connected by
	// T019's trusted launcher integration before claiming complete smoke evidence.
	handler, err := mcp.New(mcp.Options{Service: &billing.Service{Repo: store.New(source)}, Ready: source.Ready, Diagnostic: func(run, attempt string, unknown bool) {
		if unknown {
			fmt.Fprintln(os.Stderr, "mcpbench: settlement_unknown", run, attempt)
		}
	}})
	if err != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: invalid service configuration")
		os.Exit(2)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	err = source.Ready(ctx)
	cancel()
	if err != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: service unavailable")
		os.Exit(1)
	}
	server := &http.Server{Addr: ":8080", Handler: handler, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 6 * time.Second, IdleTimeout: 10 * time.Second, MaxHeaderBytes: 16384}
	if server.ListenAndServe() != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: service stopped")
		os.Exit(1)
	}
}
