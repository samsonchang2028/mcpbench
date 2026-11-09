package agent

import (
	"context"
	"encoding/json"
	"mcpbench/observability"
	"os"
	"path/filepath"
	"testing"
	"time"
)

type verifierTools struct {
	results []ToolResult
	calls   int
	block   bool
}

func (v *verifierTools) List(context.Context) ([]Tool, error) { panic("verifier must not discover") }
func (v *verifierTools) Call(ctx context.Context, n string, a json.RawMessage) (ToolResult, error) {
	v.calls++
	if v.block {
		<-ctx.Done()
		return ToolResult{}, ctx.Err()
	}
	r := v.results[0]
	v.results = v.results[1:]
	return r, nil
}
func verifierFixture(t *testing.T) (VerificationRequest, AuthInput, *observability.Writer, string, []ToolResult) {
	t.Helper()
	b, _ := os.ReadFile("../../contracts/v1/verification-request.example.json")
	var q VerificationRequest
	if e := Decode("VerificationRequest", b, &q); e != nil {
		t.Fatal(e)
	}
	now := time.Now().UTC()
	q.Budget.StartedAt = now.Add(-100 * time.Millisecond).Format("2006-01-02T15:04:05.000000Z")
	q.Budget.DeadlineAt = now.Add(29900 * time.Millisecond).Format("2006-01-02T15:04:05.000000Z")
	_, a, old, _ := fixture(t)
	old.Close()
	a.Mode = "verify"
	a.IdempotencyKey = q.IdempotencyKey
	path := filepath.Join(t.TempDir(), "events.jsonl")
	w, e := observability.New(path, observability.Context{RunID: q.RunID, AttemptID: q.AttemptID, Source: "agent"}, observability.Options{Validate: ValidateEvent, Secrets: []string{a.Capability, a.IdempotencyKey}})
	if e != nil {
		t.Fatal(e)
	}
	b, _ = os.ReadFile("../../contracts/v1/verifier-result.example.json")
	var sample VerifierResult
	json.Unmarshal(b, &sample)
	return q, a, w, path, []ToolResult{*sample.Checks[0].ToolResult, *sample.Checks[1].ToolResult}
}
func TestFixedVerifier(t *testing.T) {
	q, a, w, p, results := verifierFixture(t)
	tools := &verifierTools{results: results}
	r, e := Verify(context.Background(), q, a, tools, w)
	if e != nil || r.Status != "completed" || r.Calls != 2 || r.Retries != 0 || tools.calls != 2 || r.Budget.RemainingMS >= q.Budget.RemainingMS {
		t.Fatalf("%+v %v", r, e)
	}
	if e = w.Close(); e != nil {
		t.Fatal(e)
	}
	b, _ := os.ReadFile(p)
	parityTrace(t, b)
	parityObject(t, "VerifierResult", r)
}
func TestVerifierRejectsChangedScope(t *testing.T) {
	for _, variant := range []string{"key", "hash", "change", "expired"} {
		t.Run(variant, func(t *testing.T) {
			q, a, w, _, results := verifierFixture(t)
			switch variant {
			case "key":
				a.IdempotencyKey = "wrong-key"
			case "hash":
				q.OriginalRequestHash = q.ConfigHash
			case "change":
				q.ConflictArguments = q.OriginalArguments
			case "expired":
				q.Budget.StartedAt = time.Now().Add(-time.Minute).UTC().Format("2006-01-02T15:04:05.000000Z")
				q.Budget.DeadlineAt = time.Now().Add(-30 * time.Second).UTC().Format("2006-01-02T15:04:05.000000Z")
			}
			tools := &verifierTools{results: results}
			r, e := Verify(context.Background(), q, a, tools, w)
			if e == nil && r.Status == "completed" || tools.calls != 0 {
				t.Fatalf("accepted %s: %+v %v", variant, r, e)
			}
			w.Close()
		})
	}
}
func TestVerifierNoRepairOrRetry(t *testing.T) {
	q, a, w, p, _ := verifierFixture(t)
	tools := &verifierTools{block: true}
	ctx, cancel := context.WithTimeout(context.Background(), time.Millisecond)
	defer cancel()
	r, e := Verify(ctx, q, a, tools, w)
	if e != nil || r.Status == "completed" || r.Calls != 1 || r.Retries != 0 {
		t.Fatalf("%+v %v", r, e)
	}
	if e = w.Close(); e != nil {
		t.Fatal(e)
	}
	b, _ := os.ReadFile(p)
	parityTrace(t, b)
	parityObject(t, "VerifierResult", r)
}
func TestVerifierRejectsWrongInvoice(t *testing.T) {
	q, a, w, _, results := verifierFixture(t)
	q.InvoiceID = "INV-WRONG"
	r, e := Verify(context.Background(), q, a, &verifierTools{results: results}, w)
	if e != nil || r.Status != "failed" || r.Calls != 1 || r.Checks[0].Pass {
		t.Fatalf("%+v %v", r, e)
	}
	w.Close()
	parityObject(t, "VerifierResult", r)
}
