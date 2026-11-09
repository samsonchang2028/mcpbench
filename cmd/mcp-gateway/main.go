// Command mcp-gateway exposes only the fixed internal MCP service.
package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"mcpbench/internal/gateway"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	if run(os.Args[1:]) != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: gateway unavailable")
		os.Exit(1)
	}
}
func run(args []string) error {
	if len(args) == 1 && args[0] == "health" {
		c := &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{Proxy: nil}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
		r, e := c.Get("http://127.0.0.1:8080/healthz")
		if e != nil {
			return e
		}
		defer r.Body.Close()
		b, e := io.ReadAll(io.LimitReader(r.Body, 64))
		if e != nil || r.StatusCode != 200 || string(b) != "ready\n" {
			return fmt.Errorf("health")
		}
		return nil
	}
	if len(args) != 0 {
		return fmt.Errorf("arguments")
	}
	s := &http.Server{Addr: ":8080", Handler: gateway.New(), ReadHeaderTimeout: time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 7 * time.Second, IdleTimeout: 5 * time.Second, MaxHeaderBytes: gateway.MaxHeader, ErrorLog: log.New(io.Discard, "", 0)}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	done := make(chan struct{})
	defer close(done)
	go func() {
		select {
		case <-ctx.Done():
			c, cancel := context.WithTimeout(context.Background(), time.Second)
			defer cancel()
			s.Shutdown(c)
		case <-done:
		}
	}()
	e := s.ListenAndServe()
	if e == http.ErrServerClosed {
		return nil
	}
	return e
}
