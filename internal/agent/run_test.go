package agent

import (
	"context"
	"encoding/json"
	"errors"
	"mcpbench/internal/ollama"
	"mcpbench/observability"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

type fakeModel struct {
	messages []ollama.Request
	replies  []ollama.Response
	err      error
	wait     bool
}

func (f *fakeModel) Chat(ctx context.Context, q ollama.Request) (ollama.Response, error) {
	f.messages = append(f.messages, q)
	if f.wait {
		<-ctx.Done()
		return ollama.Response{}, ctx.Err()
	}
	if f.err != nil {
		return ollama.Response{}, f.err
	}
	if len(f.replies) == 0 {
		return ollama.Response{}, errors.New("no script")
	}
	r := f.replies[0]
	f.replies = f.replies[1:]
	return r, nil
}

type fakeTools struct {
	calls     []string
	args      []string
	fail      int
	result    ToolResult
	block     bool
	principal string
}

func (f *fakeTools) List(context.Context) ([]Tool, error) {
	out := []Tool{}
	for _, n := range []string{"billing_list_customers", "billing_list_items", CreateTool} {
		if n == CreateTool && f.principal == "billing-reader" {
			continue
		}
		out = append(out, Tool{n, "Synthetic tool", map[string]any{"type": "object", "properties": map[string]any{}}})
	}
	return out, nil
}
func (f *fakeTools) Call(ctx context.Context, n string, b json.RawMessage) (ToolResult, error) {
	f.calls = append(f.calls, n)
	f.args = append(f.args, string(b))
	if f.block {
		<-ctx.Done()
		return ToolResult{}, ctx.Err()
	}
	if f.fail > 0 {
		f.fail--
		return ToolResult{}, TransientError{}
	}
	if f.result.ToolID != "" {
		return f.result, nil
	}
	return ToolResult{ToolID: n, Result: json.RawMessage(`{"customers":[]}`)}, nil
}
func fixture(t *testing.T) (AgentRequest, AuthInput, *observability.Writer, string) {
	t.Helper()
	b, e := os.ReadFile("../../contracts/v1/agent-request.example.json")
	if e != nil {
		t.Fatal(e)
	}
	var q AgentRequest
	if e = Decode("AgentRequest", b, &q); e != nil {
		t.Fatal(e)
	}
	a := AuthInput{1, q.RunID, q.AttemptID, "agent", strings.Repeat("a", 64), "idem-test-one"}
	path := filepath.Join(t.TempDir(), "events.jsonl")
	w, e := observability.New(path, observability.Context{RunID: q.RunID, AttemptID: q.AttemptID, Source: "agent"}, observability.Options{Validate: ValidateEvent, Secrets: []string{a.Capability, a.IdempotencyKey}})
	if e != nil {
		t.Fatal(e)
	}
	return q, a, w, path
}
func answer(s string) ollama.Response {
	return ollama.Response{Done: true, Message: ollama.Message{Role: "assistant", Content: s}}
}
func selection(name, args string) ollama.Response {
	return ollama.Response{Done: true, Message: ollama.Message{Role: "assistant", ToolCalls: []ollama.ToolCall{{ID: "untrusted", Function: ollama.Function{Name: name, Arguments: json.RawMessage(args)}}}}}
}
func TestRunCorrelationAndRetry(t *testing.T) {
	q, a, w, p := fixture(t)
	f := &fakeTools{fail: 1}
	m := &fakeModel{replies: []ollama.Response{selection("billing_list_customers", `{}`), answer("Finished")}}
	r, e := (Runner{m, f, w}).Run(context.Background(), q, a)
	if e != nil || r.Status != "completed" || r.Counts != (Counts{2, 2, 1}) || len(f.calls) != 2 || f.args[0] != f.args[1] {
		t.Fatalf("result=%+v error=%v calls=%v", r, e, f.calls)
	}
	if e = w.Close(); e != nil {
		t.Fatal(e)
	}
	if m.messages[1].Messages[len(m.messages[1].Messages)-1].ToolCallID != "selection-1-1" {
		t.Fatal("lost correlation")
	}
	b, _ := os.ReadFile(p)
	if strings.Contains(string(b), a.Capability) || strings.Contains(string(b), a.IdempotencyKey) {
		t.Fatal("secret logged")
	}
	parityTrace(t, b)
}
func TestRejectAttemptsWithoutDispatch(t *testing.T) {
	for _, tc := range []struct{ name, args, principal, code string }{{"evil_tool", `{}`, "billing-drafter", "unknown_tool"}, {CreateTool, `{}`, "billing-reader", "unauthorized_attempt"}, {"billing_list_items", `{"x":1}`, "billing-drafter", "invalid_arguments"}, {"billing_list_items", `{"x":1,"x":2}`, "billing-drafter", "invalid_arguments"}, {CreateTool, `{"customer_id":"CUST-001","invoice_date":"2026-11-07","due_date":"2026-11-21","lines":[{"item_id":"SVC-CONSULT","quantity":2.0}]}`, "billing-drafter", "invalid_arguments"}} {
		t.Run(tc.code+tc.args, func(t *testing.T) {
			q, a, w, p := fixture(t)
			q.PrincipalID = tc.principal
			f := &fakeTools{principal: tc.principal}
			m := &fakeModel{replies: []ollama.Response{selection(tc.name, tc.args), answer("Recovered")}}
			r, e := (Runner{m, f, w}).Run(context.Background(), q, a)
			if e != nil || r.Counts.ToolCalls != 1 || len(f.calls) != 0 {
				t.Fatalf("%+v %v dispatches=%v", r, e, f.calls)
			}
			if e = w.Close(); e != nil {
				t.Fatal(e)
			}
			b, _ := os.ReadFile(p)
			if !strings.Contains(string(b), tc.code) {
				t.Fatal("missing evidence")
			}
			parityTrace(t, b)
		})
	}
}
func TestTimeoutAndCancellation(t *testing.T) {
	for _, cancelled := range []bool{false, true} {
		q, a, w, p := fixture(t)
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Millisecond)
		if cancelled {
			cancel()
		}
		m := &fakeModel{wait: true}
		r, e := (Runner{m, &fakeTools{}, w}).Run(ctx, q, a)
		cancel()
		if e != nil || r.Status == "completed" {
			t.Fatalf("%+v %v", r, e)
		}
		if e = w.Close(); e != nil {
			t.Fatal(e)
		}
		b, _ := os.ReadFile(p)
		parityTrace(t, b)
	}
}
func TestContextAndTurnBudgets(t *testing.T) {
	for _, overflow := range []bool{false, true} {
		q, a, w, _ := fixture(t)
		m := &fakeModel{}
		if overflow {
			q.Prompt = strings.Repeat("x", 4000)
		} else {
			for i := 0; i < 8; i++ {
				m.replies = append(m.replies, selection("billing_list_items", `{}`))
			}
		}
		r, e := (Runner{m, &fakeTools{result: ToolResult{ToolID: "billing_list_items", Result: json.RawMessage(`{"items":[]}`)}}, w}).Run(context.Background(), q, a)
		if e != nil || r.Status != "failed" || r.Counts.ModelCalls > 8 || r.Counts.ToolCalls > 12 {
			t.Fatalf("%+v %v", r, e)
		}
		if e = w.Close(); e != nil {
			t.Fatal(e)
		}
	}
}
func TestAuthAndResultRedaction(t *testing.T) {
	q, a, w, p := fixture(t)
	m := &fakeModel{replies: []ollama.Response{answer(a.Capability + " " + a.IdempotencyKey)}}
	r, e := (Runner{m, &fakeTools{}, w}).Run(context.Background(), q, a)
	if e != nil || strings.Contains(r.FinalAnswer.Text, a.Capability) || strings.Contains(r.FinalAnswer.Text, a.IdempotencyKey) {
		t.Fatal("result leaked", e)
	}
	w.Close()
	b, _ := os.ReadFile(p)
	parityTrace(t, b)
}
func TestStrictArguments(t *testing.T) {
	good := `{"customer_id":"CUST-001","invoice_date":"2026-11-07","due_date":"2026-11-21","lines":[{"item_id":"SVC-CONSULT","quantity":2}]}`
	if ValidateArguments(CreateTool, []byte(good)) != nil {
		t.Fatal("valid args rejected")
	}
	for _, b := range []string{strings.Replace(good, `"quantity":2`, `"quantity":2e0`, 1), strings.Replace(good, "2026-11-07", "2026-02-30", 1), strings.Replace(good, "2026-11-21", "2026-01-01", 1), strings.Replace(good, `"quantity":2`, `"quantity":2,"quantity":3`, 1), strings.Replace(good, `}]`, `},{"item_id":"SVC-CONSULT","quantity":1}]`, 1)} {
		if ValidateArguments(CreateTool, []byte(b)) == nil {
			t.Fatal("accepted", b)
		}
	}
	for _, b := range []string{`{"x":"\ud800"}`, `{"x":1,"x":2}`, `[] []`, `{"x":NaN}`} {
		if _, e := StrictJSON([]byte(b)); e == nil {
			t.Fatal("accepted", b)
		}
	}
}
func TestExclusiveArtifacts(t *testing.T) {
	dir := t.TempDir()
	if e := WriteResult(dir, map[string]any{"one": 1}); e != nil {
		t.Fatal(e)
	}
	if e := WriteResult(dir, map[string]any{"two": 2}); e == nil {
		t.Fatal("overwrote result")
	}
	b, _ := os.ReadFile(filepath.Join(dir, "result.json"))
	if string(b) != `{"one":1}` {
		t.Fatal(string(b))
	}
	link := filepath.Join(t.TempDir(), "link")
	os.Symlink(dir, link)
	if WriteResult(link, 1) == nil {
		t.Fatal("followed link")
	}
	if _, e := ReadDocument(filepath.Join(link, "result.json")); e == nil {
		t.Fatal("read ancestor link")
	}
}

func TestUncertainWriteRetriesUnchangedAndReportsStoredInvoice(t *testing.T) {
	q, a, w, p := fixture(t)
	b, e := os.ReadFile("../../contracts/v1/verifier-result.example.json")
	if e != nil {
		t.Fatal(e)
	}
	var sample VerifierResult
	if e = json.Unmarshal(b, &sample); e != nil {
		t.Fatal(e)
	}
	var request VerificationRequest
	b, _ = os.ReadFile("../../contracts/v1/verification-request.example.json")
	if e = json.Unmarshal(b, &request); e != nil {
		t.Fatal(e)
	}
	f := &fakeTools{fail: 1, result: *sample.Checks[0].ToolResult}
	m := &fakeModel{replies: []ollama.Response{selection(CreateTool, string(request.OriginalArguments)), answer("Saved the server invoice.")}}
	r, e := (Runner{m, f, w}).Run(context.Background(), q, a)
	if e != nil || r.Status != "completed" || r.FinalAnswer.InvoiceID == nil || *r.FinalAnswer.InvoiceID != sample.InvoiceID || r.Counts.Retries != 1 || len(f.args) != 2 || f.args[0] != f.args[1] {
		t.Fatalf("%+v %v args=%v", r, e, f.args)
	}
	for _, request := range m.messages {
		body, _ := json.Marshal(request)
		if strings.Contains(string(body), a.Capability) || strings.Contains(string(body), a.IdempotencyKey) {
			t.Fatal("trusted auth entered model request")
		}
	}
	if e = w.Close(); e != nil {
		t.Fatal(e)
	}
	events, _ := os.ReadFile(p)
	parityTrace(t, events)
	parityObject(t, "AgentResult", r)
}

func TestToolBudgetCountsRejectedAttempts(t *testing.T) {
	q, a, w, p := fixture(t)
	reply := selection("unknown", `{}`)
	for i := 1; i < 13; i++ {
		reply.Message.ToolCalls = append(reply.Message.ToolCalls, reply.Message.ToolCalls[0])
	}
	tools := &fakeTools{}
	model := &fakeModel{replies: []ollama.Response{reply}}
	r, e := (Runner{model, tools, w}).Run(context.Background(), q, a)
	if e != nil || r.Status != "failed" || r.Counts.ToolCalls != 12 || len(tools.calls) != 0 {
		t.Fatalf("%+v %v", r, e)
	}
	if e = w.Close(); e != nil {
		t.Fatal(e)
	}
	events, _ := os.ReadFile(p)
	parityTrace(t, events)
}

func TestReadDocumentRejectsFIFOWithoutWriter(t *testing.T) {
	path := filepath.Join(t.TempDir(), "input.fifo")
	if e := syscall.Mkfifo(path, 0600); e != nil {
		t.Fatal(e)
	}
	done := make(chan error, 1)
	go func() { _, e := ReadDocument(path); done <- e }()
	select {
	case e := <-done:
		if e == nil {
			t.Fatal("accepted FIFO")
		}
	case <-time.After(time.Second):
		t.Fatal("FIFO open blocked before regular-file validation")
	}
}
