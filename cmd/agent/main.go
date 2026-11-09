// Command agent implements the fixed file-mode execution and verifier entrypoints.
package main

import (
	"context"
	"fmt"
	"mcpbench/internal/agent"
	"mcpbench/internal/ollama"
	"mcpbench/observability"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

func main() {
	if execute(os.Args[1:]) != nil {
		fmt.Fprintln(os.Stderr, "mcpbench: agent failed")
		os.Exit(2)
	}
}
func execute(args []string) error {
	if len(args) != 7 || (args[0] != "run" && args[0] != "verify") || args[1] != "--request" || args[3] != "--auth" || args[5] != "--output" {
		return fmt.Errorf("invalid arguments")
	}
	request, e := agent.ReadDocument(args[2])
	if e != nil {
		return e
	}
	secret, e := agent.ReadDocument(args[4])
	if e != nil {
		return e
	}
	var auth agent.AuthInput
	if e = agent.Decode("AuthInput", secret, &auth); e != nil {
		return e
	}
	if e = agent.CheckOutput(args[6]); e != nil {
		return e
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	var q agent.AgentRequest
	var v agent.VerificationRequest
	if args[0] == "run" {
		if e = agent.Decode("AgentRequest", request, &q); e != nil {
			return e
		}
		if auth.Mode != "agent" || auth.RunID != q.RunID || auth.AttemptID != q.AttemptID {
			return fmt.Errorf("auth mismatch")
		}
		var stop context.CancelFunc
		ctx, stop = context.WithTimeout(ctx, time.Duration(q.Budgets.TaskTimeoutMS)*time.Millisecond)
		defer stop()
	} else {
		if e = agent.Decode("VerificationRequest", request, &v); e != nil {
			return e
		}
		if e = agent.ValidateVerification(v, auth); e != nil {
			return e
		}
		deadline, e := time.Parse(time.RFC3339Nano, v.Budget.DeadlineAt)
		if e != nil {
			return e
		}
		var stop context.CancelFunc
		ctx, stop = context.WithDeadline(ctx, deadline)
		defer stop()
	}
	w, e := observability.New(filepath.Join(args[6], "events.jsonl"), observability.Context{RunID: auth.RunID, AttemptID: auth.AttemptID, Source: "agent"}, observability.Options{Validate: agent.ValidateEvent, Secrets: []string{auth.Capability, auth.IdempotencyKey}})
	if e != nil {
		return e
	}
	defer w.Close()
	connectionCtx, stop := context.WithTimeout(ctx, 5*time.Second)
	tools, e := agent.ConnectMCP(connectionCtx, auth)
	stop()
	if e != nil {
		return e
	}
	defer tools.Close()
	var result any
	status := "failed"
	if args[0] == "run" {
		r, err := (agent.Runner{Model: ollama.New(), Tools: tools, Events: w}).Run(ctx, q, auth)
		e = err
		result = r
		status = r.Status
	} else {
		r, err := agent.Verify(ctx, v, auth, tools, w)
		e = err
		result = r
		status = r.Status
	}
	if e != nil {
		return e
	}
	if e = w.Close(); e != nil {
		return e
	}
	if e = agent.WriteResult(args[6], result); e != nil {
		return e
	}
	if status != "completed" {
		return fmt.Errorf("execution failed")
	}
	return nil
}
