package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"mcpbench/internal/agent"
	"mcpbench/internal/ollama"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type failedTools struct {
	closed bool
	calls  int
}

func (*failedTools) List(context.Context) ([]agent.Tool, error) {
	return nil, errors.New("synthetic discovery failure")
}
func (f *failedTools) Call(context.Context, string, json.RawMessage) (agent.ToolResult, error) {
	f.calls++
	return agent.ToolResult{}, errors.New("synthetic verification failure")
}
func (f *failedTools) Close() error { f.closed = true; return nil }

func TestFailedTerminalResultsArePublished(t *testing.T) {
	for _, mode := range []string{"run", "verify", "setup"} {
		t.Run(mode, func(t *testing.T) {
			filename := "agent-request.example.json"
			if mode == "verify" {
				filename = "verification-request.example.json"
			}
			raw, e := os.ReadFile("../../../contracts/v1/" + filename)
			if e != nil {
				t.Fatal(e)
			}
			var req map[string]any
			if e = json.Unmarshal(raw, &req); e != nil {
				t.Fatal(e)
			}
			a := agent.AuthInput{SchemaVersion: 1, RunID: req["run_id"].(string), AttemptID: req["attempt_id"].(string), Mode: "agent", Capability: strings.Repeat("a", 64), IdempotencyKey: "idem-scripted-terminal"}
			if mode == "verify" {
				a.Mode = "verify"
				a.IdempotencyKey = req["idempotency_key"].(string)
				budget := req["budget"].(map[string]any)
				now := time.Now().UTC()
				budget["started_at"] = now.Add(-100 * time.Millisecond).Format("2006-01-02T15:04:05.000000Z")
				budget["deadline_at"] = now.Add(29900 * time.Millisecond).Format("2006-01-02T15:04:05.000000Z")
			}
			dir := t.TempDir()
			output := filepath.Join(dir, "output")
			if e = os.Mkdir(output, 0700); e != nil {
				t.Fatal(e)
			}
			request := filepath.Join(dir, "request.json")
			auth := filepath.Join(dir, "auth.json")
			for path, value := range map[string]any{request: req, auth: a} {
				b, e := json.Marshal(value)
				if e != nil {
					t.Fatal(e)
				}
				if e = os.WriteFile(path, b, 0600); e != nil {
					t.Fatal(e)
				}
			}
			tools := &failedTools{}
			command := mode
			if command == "setup" {
				command = "run"
			}
			e = executeWithConnector([]string{command, "--request", request, "--auth", auth, "--output", output}, func(context.Context, agent.AuthInput) (toolConnection, error) {
				if mode == "setup" {
					return nil, errors.New("synthetic setup failure")
				}
				return tools, nil
			})
			if e == nil {
				t.Fatal("failed child returned success")
			}
			b, e := os.ReadFile(filepath.Join(output, "result.json"))
			if mode == "setup" {
				if !os.IsNotExist(e) {
					t.Fatal("setup invented result", e)
				}
				return
			}
			if e != nil {
				t.Fatal("valid terminal result lost:", e)
			}
			if !tools.closed {
				t.Fatal("connection not closed")
			}
			var status string
			if mode == "run" {
				var result agent.AgentResult
				if e = agent.Decode("AgentResult", b, &result); e != nil {
					t.Fatal(e)
				}
				status = result.Status
				if result.Counts != (agent.Counts{}) {
					t.Fatal("invented calls", result.Counts)
				}
			} else {
				var result agent.VerifierResult
				if e = agent.Decode("VerifierResult", b, &result); e != nil {
					t.Fatal(e)
				}
				status = result.Status
				if result.Calls != 1 || result.Retries != 0 || tools.calls != 1 {
					t.Fatal("verification counts changed", result)
				}
			}
			if status != "failed" {
				t.Fatal("failed outcome changed:", status)
			}
			trace, e := os.ReadFile(filepath.Join(output, "events.jsonl"))
			if e != nil {
				t.Fatal(e)
			}
			if !strings.Contains(string(trace), `"failure"`) {
				t.Fatal("failure trace lost")
			}
			for _, line := range strings.Split(strings.TrimSpace(string(trace)), "\n") {
				var event map[string]any
				if e = json.Unmarshal([]byte(line), &event); e != nil {
					t.Fatal(e)
				}
				if e = agent.ValidateEvent(event); e != nil {
					t.Fatal("bad event", e)
				}
			}
		})
	}
}

func TestScriptedModelReadsCompleteBusinessContent(t *testing.T) {
	model := &scriptedModel{turn: 3}
	for _, content := range []string{`{"invoice":{"invoice_id":"INV-SYNTHETIC"},"lines":[]}`, `{"tool_id":"billing_create_draft_invoice","is_error":true,"error":{"code":"db_error"}}`} {
		response, e := model.Chat(context.Background(), ollama.Request{Messages: []ollama.Message{{Role: "tool", ToolName: agent.CreateTool, Content: content}}})
		if strings.Contains(content, "INV-SYNTHETIC") {
			if e != nil || response.Message.Content != "Created draft INV-SYNTHETIC." {
				t.Fatal(response, e)
			}
		} else if e == nil {
			t.Fatal("error envelope became a success")
		}
	}
}

// Exercise the changed scripted parser through the actual CLI loop, with the
// complete development business responses. These are in-memory calls, not SQL.
type replayTools struct {
	catalog []agent.Tool
	results map[string]agent.ToolResult
	calls   int
}

func (r *replayTools) List(context.Context) ([]agent.Tool, error) { return r.catalog, nil }
func (r *replayTools) Call(_ context.Context, name string, _ json.RawMessage) (agent.ToolResult, error) {
	r.calls++
	return r.results[name], nil
}
func (*replayTools) Close() error { return nil }

func TestScriptedCLICompleteHistoryAndOverflow(t *testing.T) {
	for _, extra := range []int{0, 21} {
		t.Run(fmt.Sprintf("extra-%d", extra), func(t *testing.T) {
			raw, e := os.ReadFile("../../../internal/agent/testdata/full-context-history.json")
			if e != nil {
				t.Fatal(e)
			}
			var history ollama.Request
			if e = json.Unmarshal(raw, &history); e != nil {
				t.Fatal(e)
			}
			tools := &replayTools{results: map[string]agent.ToolResult{}}
			for _, tool := range history.Tools {
				tools.catalog = append(tools.catalog, agent.Tool{Name: tool.Function.Name, Description: tool.Function.Description, InputSchema: tool.Function.Parameters})
			}
			for _, message := range history.Messages {
				if message.Role == "tool" {
					var result agent.ToolResult
					if e = json.Unmarshal([]byte(message.Content), &result); e != nil {
						t.Fatal(e)
					}
					tools.results[result.ToolID] = result
				}
			}
			raw, e = os.ReadFile("../../../contracts/v1/agent-request.example.json")
			if e != nil {
				t.Fatal(e)
			}
			var q agent.AgentRequest
			if e = json.Unmarshal(raw, &q); e != nil {
				t.Fatal(e)
			}
			q.Model.Tag = "scripted-t019-smoke"
			q.Prompt += strings.Repeat("x", extra)
			a := agent.AuthInput{SchemaVersion: 1, RunID: q.RunID, AttemptID: q.AttemptID, Mode: "agent", Capability: strings.Repeat("a", 64), IdempotencyKey: "idem-scripted-history"}
			dir := t.TempDir()
			output := filepath.Join(dir, "output")
			if e = os.Mkdir(output, 0700); e != nil {
				t.Fatal(e)
			}
			request := filepath.Join(dir, "request.json")
			auth := filepath.Join(dir, "auth.json")
			for path, value := range map[string]any{request: q, auth: a} {
				raw, e = json.Marshal(value)
				if e != nil {
					t.Fatal(e)
				}
				if e = os.WriteFile(path, raw, 0600); e != nil {
					t.Fatal(e)
				}
			}
			e = executeWithConnector([]string{"run", "--request", request, "--auth", auth, "--output", output}, func(context.Context, agent.AuthInput) (toolConnection, error) { return tools, nil })
			if (e != nil) != (extra > 0) {
				t.Fatalf("unexpected child result: %v", e)
			}
			raw, e = os.ReadFile(filepath.Join(output, "result.json"))
			if e != nil {
				t.Fatal(e)
			}
			var result agent.AgentResult
			if e = agent.Decode("AgentResult", raw, &result); e != nil {
				t.Fatal(e)
			}
			if tools.calls != 3 {
				t.Fatal("business calls missing", tools.calls)
			}
			if extra == 0 {
				if result.Status != "completed" || result.Counts != (agent.Counts{ModelCalls: 4, ToolCalls: 3}) || result.FinalAnswer.InvoiceID == nil || *result.FinalAnswer.InvoiceID != "INV-1FE3C5398ABE8BC078918EEF8DF44A72" || !strings.Contains(result.FinalAnswer.Text, *result.FinalAnswer.InvoiceID) {
					t.Fatal("scripted final answer lost", result)
				}
			} else if result.Status != "failed" || result.Counts != (agent.Counts{ModelCalls: 3, ToolCalls: 3}) || result.FinalAnswer.InvoiceID != nil {
				t.Fatal("failed counts/status changed", result)
			}
		})
	}
}
