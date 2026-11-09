package mcp

import (
	"encoding/json"
	"mcpbench/internal/billing"
	"mcpbench/observability"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDatabaseEventsActualOutcomesAndPythonParity(t *testing.T) {
	path := filepath.Join(t.TempDir(), "events.jsonl")
	w, err := observability.New(path, observability.Context{RunID: "run-test", AttemptID: "attempt-test", Source: "mcp"}, observability.Options{Validate: ValidateEvent})
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		op  string
		err error
	}{{"read_tool", nil}, {"create_draft", nil}, {"replay", billing.Fail("idempotency_conflict")}, {"create_draft", &billing.Error{Code: "db_error", OutcomeUnknown: true}}} {
		phase := "execution"
		if tc.op == "replay" {
			phase = "verification"
		}
		close, err := databaseObserver(w, phase, "tool-parent")(tc.op, "tx-test")
		if err != nil {
			t.Fatal(err)
		}
		if err = close(tc.err); err != nil {
			t.Fatal(err)
		}
	}
	if err = w.Close(); err != nil {
		t.Fatal(err)
	}
	raw, _ := os.ReadFile(path)
	parityTrace(t, raw)
	if !strings.Contains(string(raw), `"attribution":"uncertain"`) {
		t.Fatal("unknown ACK became positive evidence")
	}
}
func TestTraceFilesPhaseContinuityAndFailClosedSecrets(t *testing.T) {
	base := t.TempDir()
	config := filepath.Join(base, "config.json")
	output := filepath.Join(base, "events")
	os.Mkdir(output, 0700)
	write := func(phase string, secrets []string) {
		b, _ := json.Marshal(TraceConfig{1, "run-test", "attempt-test", phase, secrets})
		if err := os.WriteFile(config, b, 0600); err != nil {
			t.Fatal(err)
		}
	}
	write("execution", []string{token})
	manager := TraceFiles{Config: config, Output: output}
	defer manager.Close()
	first, phase, err := manager.Events("run-test", "attempt-test")
	if err != nil || phase != "execution" {
		t.Fatal(err)
	}
	secondToken := strings.Repeat("b", 64)
	write("verification", []string{token, secondToken})
	second, phase, err := manager.Events("run-test", "attempt-test")
	if err != nil || phase != "verification" || first != second {
		t.Fatal("writer reset on verification", err)
	}
	write("execution", []string{token, secondToken})
	if _, _, err = manager.Events("run-test", "attempt-test"); err == nil {
		t.Fatal("phase rollback admitted")
	}
	write("verification", []string{token, secondToken})
	if _, _, err = manager.Events("wrong-run", "attempt-test"); err == nil {
		t.Fatal("foreign run admitted")
	}
	// A token minted after writer creation is installed before the factory
	// returns; it is redacted without starting a second MCP source sequence.
	if err := first.Emit(observability.Record{Type: "tool.started", Phase: "verification", Status: "ok", CallID: "tool-test", Data: map[string]any{"tool_id": billing.ListCustomers, "arguments": map[string]any{}, "retry_index": 0}}); err != nil {
		t.Fatal(err)
	}
	if err := first.Emit(observability.Record{Type: "tool.completed", Phase: "verification", Status: "ok", CallID: "tool-test", Data: map[string]any{"tool_id": billing.ListCustomers, "duration_ms": 1, "tool_result": map[string]any{"tool_id": billing.ListCustomers, "is_error": false, "result": map[string]any{"customers": []any{map[string]any{"customer_id": "CUST-001", "name": secondToken, "active": true}}}}}}); err != nil {
		t.Fatal(err)
	}
	raw, _ := os.ReadFile(filepath.Join(output, "events.jsonl"))
	if strings.Contains(string(raw), secondToken) || !strings.Contains(string(raw), observability.Redacted) {
		t.Fatal("new capability not redacted")
	}
}
