package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"mcpbench/internal/ollama"
	"os"
	"reflect"
	"strings"
	"testing"
)

// Captured development-only synthetic response shapes, including full expanded
// schemas and business IDs/timestamps. No runtime artifact or service is needed.
type historyTools struct {
	catalog []Tool
	results []ToolResult
}

func (h *historyTools) List(context.Context) ([]Tool, error) { return h.catalog, nil }
func (h *historyTools) Call(_ context.Context, name string, _ json.RawMessage) (ToolResult, error) {
	r := h.results[0]
	h.results = h.results[1:]
	if r.ToolID != name {
		panic("unexpected replay order")
	}
	return r, nil
}
func TestFullContextCompleteBusinessHistory(t *testing.T) {
	for _, extra := range []int{0, 20, 21} {
		t.Run(fmt.Sprintf("extra-%d", extra), func(t *testing.T) {
			q, a, w, path := fixture(t)
			q.Model.Tag = "scripted-t019-smoke"
			q.Prompt += strings.Repeat("x", extra)
			raw, e := os.ReadFile("testdata/full-context-history.json")
			if e != nil {
				t.Fatal(e)
			}
			var history ollama.Request
			if e = json.Unmarshal(raw, &history); e != nil {
				t.Fatal(e)
			}
			tools := &historyTools{}
			for _, tool := range history.Tools {
				tools.catalog = append(tools.catalog, Tool{tool.Function.Name, tool.Function.Description, tool.Function.Parameters})
			}
			model := &fakeModel{}
			for i := 2; i < len(history.Messages); i += 2 {
				model.replies = append(model.replies, ollama.Response{Done: true, Message: history.Messages[i]})
				var result ToolResult
				if e = json.Unmarshal([]byte(history.Messages[i+1].Content), &result); e != nil {
					t.Fatal(e)
				}
				tools.results = append(tools.results, result)
			}
			model.replies = append(model.replies, answer("Created draft INV-1FE3C5398ABE8BC078918EEF8DF44A72."))
			result, e := (Runner{model, tools, w}).Run(context.Background(), q, a)
			if e != nil {
				t.Fatal(e)
			}
			if e = w.Close(); e != nil {
				t.Fatal(e)
			}
			if extra <= 20 {
				if result.Status != "completed" || result.Counts != (Counts{4, 3, 0}) || result.FinalAnswer.InvoiceID == nil || *result.FinalAnswer.InvoiceID != "INV-1FE3C5398ABE8BC078918EEF8DF44A72" {
					t.Fatalf("full history did not finish: %+v", result)
				}
				final := model.messages[3]
				encoded, _ := json.Marshal(final)
				if len(encoded) != 3564+extra || len(encoded)+q.Budgets.OutputTokens > q.Budgets.ContextTokens {
					t.Fatalf("wrong guarded size: %d", len(encoded))
				}
				if !reflect.DeepEqual(final.Tools, history.Tools) {
					t.Fatal("full schemas changed")
				}
				for i := 2; i < len(history.Messages); i += 2 {
					// Assistant selections and tool correlation survive; every business field
					// must survive as well, rather than a total-only or truncated summary.
					if !reflect.DeepEqual(final.Messages[i], history.Messages[i]) {
						t.Fatal("assistant selection changed")
					}
					old, next := history.Messages[i+1], final.Messages[i+1]
					var envelope ToolResult
					json.Unmarshal([]byte(old.Content), &envelope)
					if next.Role != old.Role || next.ToolName != old.ToolName || next.ToolCallID != old.ToolCallID || next.Content != string(envelope.Result) {
						t.Fatalf("business or correlation lost: %+v", next)
					}
				}
			} else if result.Status != "failed" || result.Counts != (Counts{3, 3, 0}) {
				t.Fatalf("one byte overflow admitted: %+v", result)
			}
			trace, e := os.ReadFile(path)
			if e != nil {
				t.Fatal(e)
			}
			if extra > 20 && !strings.Contains(string(trace), `"code":"context_overflow"`) {
				t.Fatal("overflow evidence lost")
			}
			// Internal/event envelopes stay complete even when model Content is projected.
			if !strings.Contains(string(trace), `"is_error":false`) || !strings.Contains(string(trace), `"total_cents":25000`) {
				t.Fatal("internal result envelope lost")
			}
			parityTrace(t, trace)
			parityObject(t, "AgentResult", result)
		})
	}
}

func TestToolErrorContentKeepsEnvelope(t *testing.T) {
	q, a, w, _ := fixture(t)
	expected := ToolResult{ToolID: "billing_list_items", IsError: true, Error: &ToolError{Code: "db_error", Message: "Temporary failure.", Retryable: false}}
	model := &fakeModel{replies: []ollama.Response{selection("billing_list_items", `{}`), answer("Failed safely")}}
	result, e := (Runner{model, &fakeTools{result: expected}, w}).Run(context.Background(), q, a)
	if e != nil {
		t.Fatal(e)
	}
	if e = w.Close(); e != nil {
		t.Fatal(e)
	}
	if result.Counts != (Counts{2, 1, 0}) {
		t.Fatal(result.Counts)
	}
	var actual ToolResult
	if e = json.Unmarshal([]byte(model.messages[1].Messages[3].Content), &actual); e != nil || !reflect.DeepEqual(actual, expected) {
		t.Fatalf("error envelope changed: %+v %v", actual, e)
	}
}
