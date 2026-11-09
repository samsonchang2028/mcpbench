package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"mcpbench/internal/ollama"
	"os"
	"os/exec"
	"testing"
	"time"
)

// The runtime validator deliberately supports only events this producer emits.
// Every accepted kind and its nested semantic constraints are checked against
// the authoritative Python contract here; no subprocess is used at runtime.
func TestEventSemanticParity(t *testing.T) {
	q, a, w, path := fixture(t)
	model := &fakeModel{replies: []ollama.Response{selection("unknown", `{}`), selection("billing_list_items", `{}`), answer("Done")}}
	tools := &fakeTools{fail: 1, result: ToolResult{ToolID: "billing_list_items", Result: json.RawMessage(`{"items":[]}`)}}
	if _, e := (Runner{model, tools, w}).Run(context.Background(), q, a); e != nil {
		t.Fatal(e)
	}
	if e := w.Close(); e != nil {
		t.Fatal(e)
	}
	raw, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	events := map[string]map[string]any{}
	for _, line := range bytes.Split(bytes.TrimSpace(raw), []byte("\n")) {
		var v map[string]any
		if json.Unmarshal(line, &v) != nil {
			t.Fatal("bad event")
		}
		events[v["event_type"].(string)] = v
	}
	clone := func(kind string) map[string]any {
		b, _ := json.Marshal(events[kind])
		var v map[string]any
		json.Unmarshal(b, &v)
		return v
	}
	var cases []map[string]any
	add := func(v map[string]any) { cases = append(cases, v) }
	for _, v := range events {
		if ValidateEvent(v) != nil {
			t.Fatal("rejected emitted event")
		}
		add(v)
	}
	mutate := func(kind string, f func(map[string]any, map[string]any)) {
		v := clone(kind)
		f(v, v["data"].(map[string]any))
		if ValidateEvent(v) == nil {
			t.Fatalf("accepted invalid %s: %v", kind, v)
		}
		add(v)
	}
	mutate("model.completed", func(v, d map[string]any) {
		d["prompt_tokens"] = 1
		d["output_tokens"] = 2
		d["counts_unavailable_reason"] = "unsupported"
	})
	mutate("model.completed", func(v, d map[string]any) { d["counts_unavailable_reason"] = nil })
	mutate("tool.started", func(v, d map[string]any) { d["arguments"] = map[string]any{"unexpected": true} })
	mutate("tool.completed", func(v, d map[string]any) { d["tool_id"] = CreateTool })
	mutate("tool.completed", func(v, d map[string]any) {
		d["tool_result"] = tree(ToolResult{ToolID: "billing_list_items", IsError: true, Error: &ToolError{"db_error", "Failure.", false}})
	})
	mutate("tool.failed", func(v, d map[string]any) {
		d["tool_result"] = tree(ToolResult{ToolID: "billing_list_items", Result: json.RawMessage(`{"items":[]}`)})
	})
	mutate("tool.failed", func(v, d map[string]any) {
		d["tool_result"] = tree(ToolResult{ToolID: "billing_list_items", IsError: true, Error: &ToolError{"authorization_denied", "Denied.", true}})
	})
	mutate("agent.finished", func(v, d map[string]any) { d["result"].(map[string]any)["run_id"] = "different-run" })
	mutate("failure", func(v, d map[string]any) { d["failure"].(map[string]any)["code"] = "verification_failed" })
	mutate("failure", func(v, d map[string]any) { d["extra"] = true })
	// Python compares each individual shape/semantic verdict, independently of
	// stream correlation (covered separately by parityTrace).
	input := []map[string]any{}
	for _, v := range cases {
		input = append(input, map[string]any{"event": v, "valid": ValidateEvent(v) == nil})
	}
	b, _ := json.Marshal(input)
	python := os.Getenv("MCPBENCH_TEST_PYTHON")
	if python == "" {
		t.Fatal("MCPBENCH_TEST_PYTHON required")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, python, "-c", `import json,sys
from contracts.validate import validate
for case in json.load(sys.stdin):
 try:
  validate("Event",case["event"])
  valid=True
 except Exception:
  valid=False
 assert valid == case["valid"],case
`)
	cmd.Dir = "../.."
	cmd.Stdin = bytes.NewReader(b)
	if output, e := cmd.CombinedOutput(); e != nil {
		t.Fatalf("semantic parity failed: %v %s", e, output)
	}
}
