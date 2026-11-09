package main

import (
	"context"
	"encoding/json"
	"mcpbench/internal/agent"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestEntrypointFailsBeforeNetwork(t *testing.T) {
	for _, args := range [][]string{nil, {"run"}, {"other", "--request", "x", "--auth", "y", "--output", "z"}, {"run", "--auth", "x", "--request", "y", "--output", "z"}} {
		if execute(args) == nil {
			t.Fatal("accepted invalid fixed arguments")
		}
	}
	dir := t.TempDir()
	request := filepath.Join(dir, "request.json")
	auth := filepath.Join(dir, "auth.json")
	output := filepath.Join(dir, "output")
	if e := os.Mkdir(output, 0700); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(request, []byte(`{"schema_version":1,"schema_version":1}`), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(auth, []byte(`{}`), 0600); e != nil {
		t.Fatal(e)
	}
	if execute([]string{"run", "--request", request, "--auth", auth, "--output", output}) == nil {
		t.Fatal("accepted invalid documents")
	}
	entries, _ := os.ReadDir(output)
	if len(entries) != 0 {
		t.Fatal("invalid input published artifacts")
	}
}

// The connector is an owned fake: no MCP or model service is contacted.
type startupTools struct {
	results []agent.ToolResult
	calls   int
}

func (s *startupTools) List(context.Context) ([]agent.Tool, error) { panic("verify must not discover") }
func (s *startupTools) Close() error                               { return nil }
func (s *startupTools) Call(ctx context.Context, name string, args json.RawMessage) (agent.ToolResult, error) {
	if ctx.Err() != nil {
		return agent.ToolResult{}, ctx.Err()
	}
	s.calls++
	r := s.results[0]
	s.results = s.results[1:]
	return r, nil
}

func TestVerifierStartupConsumesAndCapsBudget(t *testing.T) {
	for _, tc := range []struct {
		name            string
		remaining, wall time.Duration
		exhaust         bool
	}{
		{"startup-charged", time.Second, 29 * time.Second, false},
		{"remaining-exhausted", 50 * time.Millisecond, 29 * time.Second, true},
		{"wall-exhausted", time.Second, 50 * time.Millisecond, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			b, e := os.ReadFile("../../contracts/v1/verification-request.example.json")
			if e != nil {
				t.Fatal(e)
			}
			var q agent.VerificationRequest
			if e = json.Unmarshal(b, &q); e != nil {
				t.Fatal(e)
			}
			now := time.Now().UTC()
			deadline := now.Add(tc.wall)
			q.Budget.StartedAt = deadline.Add(-30 * time.Second).Format("2006-01-02T15:04:05.000000Z")
			q.Budget.DeadlineAt = deadline.Format("2006-01-02T15:04:05.000000Z")
			q.Budget.RemainingMS = float64(tc.remaining / time.Millisecond)
			q.Budget.ElapsedMS = 30000 - q.Budget.RemainingMS
			q.Budget.OperationTimeoutMS = q.Budget.RemainingMS
			a := agent.AuthInput{SchemaVersion: 1, RunID: q.RunID, AttemptID: q.AttemptID, Mode: "verify", Capability: strings.Repeat("a", 64), IdempotencyKey: q.IdempotencyKey}
			if e = agent.ValidateVerification(q, a); e != nil {
				t.Fatal(e)
			}
			dir := t.TempDir()
			request, auth, output := filepath.Join(dir, "request.json"), filepath.Join(dir, "auth.json"), filepath.Join(dir, "output")
			if e = os.Mkdir(output, 0700); e != nil {
				t.Fatal(e)
			}
			for path, value := range map[string]any{request: q, auth: a} {
				b, e := json.Marshal(value)
				if e != nil {
					t.Fatal(e)
				}
				if e = os.WriteFile(path, b, 0600); e != nil {
					t.Fatal(e)
				}
			}
			b, e = os.ReadFile("../../contracts/v1/verifier-result.example.json")
			if e != nil {
				t.Fatal(e)
			}
			var sample agent.VerifierResult
			if e = json.Unmarshal(b, &sample); e != nil {
				t.Fatal(e)
			}
			tools := &startupTools{results: []agent.ToolResult{*sample.Checks[0].ToolResult, *sample.Checks[1].ToolResult}}
			var startup time.Duration
			e = executeWithConnector([]string{"verify", "--request", request, "--auth", auth, "--output", output}, func(ctx context.Context, _ agent.AuthInput) (toolConnection, error) {
				start := time.Now()
				capAt, ok := ctx.Deadline()
				if !ok || capAt.After(start.Add(tc.remaining)) || capAt.After(deadline) {
					t.Fatal("connection escaped remaining/deadline cap")
				}
				if tc.exhaust {
					<-ctx.Done()
				} else {
					time.Sleep(80 * time.Millisecond)
				}
				startup = time.Since(start)
				return tools, nil
			})
			if (e != nil) != tc.exhaust {
				t.Fatalf("execution error=%v", e)
			}
			b, e = os.ReadFile(filepath.Join(output, "result.json"))
			if e != nil {
				t.Fatal(e)
			}
			var result agent.VerifierResult
			if e = json.Unmarshal(b, &result); e != nil {
				t.Fatal(e)
			}
			if result.Budget.ElapsedMS < q.Budget.ElapsedMS+float64(startup.Microseconds())/1000 {
				t.Fatalf("startup cost lost: %+v, cost=%v", result.Budget, startup)
			}
			if tc.exhaust {
				if tools.calls != 0 || result.Calls != 0 || result.Status != "timeout" {
					t.Fatalf("work after budget exhaustion: %+v", result)
				}
			} else if tools.calls != 2 || result.Status != "completed" {
				t.Fatalf("unexpected result: %+v", result)
			}
			// Validate startup-expired results and their pre-call failure trace with
			// the real Python contract, including the budget observation semantics.
			python := os.Getenv("MCPBENCH_TEST_PYTHON")
			if python == "" {
				t.Fatal("MCPBENCH_TEST_PYTHON required")
			}
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, python, "-c", `import sys
from pathlib import Path
from contracts.validate import load_bytes,validate,validate_event_stream
p=Path(sys.argv[1])
validate("VerifierResult",load_bytes((p/"result.json").read_bytes()))
es=[load_bytes(x) for x in (p/"events.jsonl").read_bytes().splitlines()]
for e in es: validate("Event",e)
validate_event_stream(es)
`, output)
			cmd.Dir = "../.."
			if out, e := cmd.CombinedOutput(); e != nil {
				t.Fatalf("startup artifact parity: %v %s", e, out)
			}
		})
	}
}
