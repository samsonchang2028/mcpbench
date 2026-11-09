// Command billing-mcp serves only the synthetic billing MCP endpoint.
package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"mcpbench/internal/billing"
	"mcpbench/internal/mcp"
	"mcpbench/internal/store"
)

func main() {
	if err := execute(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: service unavailable")
		os.Exit(1)
	}
}
func execute(args []string) (returned error) {
	if len(args) == 1 && args[0] == "health" {
		client := &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{Proxy: nil}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
		response, err := client.Get("http://127.0.0.1:8080/healthz")
		if err != nil {
			return err
		}
		defer response.Body.Close()
		raw, err := io.ReadAll(io.LimitReader(response.Body, 64))
		if err != nil || response.StatusCode != 200 || string(raw) != "ready\n" {
			return fmt.Errorf("health")
		}
		return nil
	}
	if len(args) != 0 {
		return fmt.Errorf("arguments")
	}
	source, err := mcp.ServiceSource()
	if err != nil {
		return err
	}
	traces := &mcp.TraceFiles{Config: "/run/mcpbench/trace/config.json", Output: "/run/mcpbench/events"}
	defer func() {
		if err := traces.Close(); err != nil {
			returned = err
		}
	}()
	handler, err := mcp.New(mcp.Options{Service: &billing.Service{Repo: store.New(source)}, Ready: source.Ready, Events: traces.Events, Diagnostic: func(run, attempt string, unknown bool) {
		if unknown {
			fmt.Fprintln(os.Stderr, "mcpbench: settlement_unknown", run, attempt)
		}
	}})
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	err = source.Ready(ctx)
	cancel()
	if err != nil {
		return err
	}
	server := &http.Server{Addr: ":8080", Handler: handler, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 6 * time.Second, IdleTimeout: 10 * time.Second, MaxHeaderBytes: 16384}
	stopped, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	done := make(chan struct{})
	go func() {
		select {
		case <-stopped.Done():
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			server.Shutdown(ctx)
		case <-done:
		}
	}()
	err = server.ListenAndServe()
	close(done)
	if err == http.ErrServerClosed {
		return nil
	}
	return err
}
