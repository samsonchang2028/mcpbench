package observability

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// The runtime package never starts a process. This TEST-ONLY adapter exercises
// the frozen authoritative Python Event validator instead of a permissive stub.
func python(t *testing.T, program string, input []byte) error {
	t.Helper()
	binary := os.Getenv("MCPBENCH_TEST_PYTHON")
	if binary == "" {
		t.Fatal("set MCPBENCH_TEST_PYTHON to the existing pinned T008 .venv/bin/python")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, binary, "-c", program)
	command.Dir = ".."
	command.Env = []string{"LANG=C.UTF-8", "PATH=/usr/local/bin:/usr/bin:/bin"}
	command.Stdin = bytes.NewReader(input)
	// Never echo exception text or submitted objects in a validation error.
	if err := command.Run(); err != nil {
		return errors.New("contract validation failed")
	}
	return nil
}
func contract(t *testing.T) Validator {
	return func(event map[string]any) error {
		raw, err := json.Marshal(event)
		if err != nil {
			return err
		}
		return python(t,
			"import sys; from contracts.validate import load_bytes,validate; validate('Event',load_bytes(sys.stdin.buffer.read()))", raw)
	}
}
func makeWriter(t *testing.T, options Options) (*Writer, string) {
	t.Helper()
	if options.Validate == nil {
		options.Validate = contract(t)
	}
	if options.Now == nil {
		options.Now = func() time.Time { return time.Date(2026, 11, 8, 19, 0, 0, 0, time.UTC) }
	}
	path := filepath.Join(t.TempDir(), "events.jsonl")
	writer, err := New(path, Context{"run-test", "attempt-test", "agent"}, options)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = writer.Close() })
	return writer, path
}
func start() Record {
	return Record{Type: "model.started", Phase: "agent", Status: "ok", CallID: "call-one", ParentCallID: "parent-one", Data: map[string]any{"model_digest": strings.Repeat("a", 64), "prompt_hash": strings.Repeat("a", 64)}}
}
func end() Record {
	return Record{Type: "model.completed", Phase: "agent", Status: "ok", CallID: "call-one", ParentCallID: "parent-one", Data: map[string]any{"model_digest": strings.Repeat("a", 64), "prompt_hash": strings.Repeat("a", 64), "duration_ms": 4, "prompt_tokens": 12, "output_tokens": 7, "counts_unavailable_reason": nil}}
}
func failure(reason string) Record {
	return Record{Type: "failure", Phase: "agent", Status: "error", Data: map[string]any{"failure": map[string]any{"stage": "agent", "code": "protocol_error", "call_id": nil, "reason": reason, "attribution": "observed", "disposition": "terminal"}}}
}
func readEvents(t *testing.T, path string) []map[string]any {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var events []map[string]any
	for _, line := range bytes.Split(bytes.TrimSpace(raw), []byte("\n")) {
		var event map[string]any
		if err := json.Unmarshal(line, &event); err != nil {
			t.Fatal(err)
		}
		events = append(events, event)
	}
	return events
}
func TestDurableSequenceCorrelationAndContract(t *testing.T) {
	now := time.Date(2026, 11, 8, 19, 0, 0, 0, time.UTC)
	writer, path := makeWriter(t, Options{Now: func() time.Time { return now }})
	if writer.Summary().ArtifactComplete {
		t.Fatal("open trace complete")
	}
	if err := writer.Emit(start()); err != nil {
		t.Fatal(err)
	}
	now = now.Add(4 * time.Millisecond)
	if err := writer.Emit(end()); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	events := readEvents(t, path)
	raw, _ := json.Marshal(events)
	if err := python(t, "import sys; from contracts.validate import load_bytes,validate_event_stream; validate_event_stream(load_bytes(sys.stdin.buffer.read()))", raw); err != nil {
		t.Fatal(err)
	}
	if events[1]["elapsed_ms"] != float64(4) || events[1]["sequence"] != float64(2) || events[1]["parent_call_id"] != "parent-one" {
		t.Fatal("lost context/timing")
	}
	info, _ := os.Stat(path)
	summary := writer.Summary()
	if info.Mode().Perm() != 0600 || summary.Bytes != int(info.Size()) || !summary.ArtifactComplete {
		t.Fatalf("bad durable summary: %+v", summary)
	}
}
func TestMissingAndRejectingValidator(t *testing.T) {
	_, err := New(filepath.Join(t.TempDir(), "events"), Context{"run-test", "attempt-test", "agent"}, Options{})
	if err != LogError("validator_required") {
		t.Fatal(err)
	}
	observed := false
	writer, _ := makeWriter(t, Options{Secrets: []string{"literal-private"}, Validate: func(event map[string]any) error {
		raw, _ := json.Marshal(event)
		if bytes.Contains(raw, []byte("literal-private")) {
			t.Fatal("validator received secret")
		}
		observed = true
		return errors.New("private validation detail")
	}})
	if err := writer.Emit(failure("literal-private")); err != LogError("event") {
		t.Fatal(err)
	}
	if !observed || writer.Summary().ArtifactComplete {
		t.Fatal("validator not enforced")
	}
	if err := writer.Close(); err != LogError("event") {
		t.Fatal("first failure lost", err)
	}
}
func TestRedactionAndMetricPreservation(t *testing.T) {
	value := map[string]any{"password": "private", "prompt_tokens": 12, "output_tokens": 7, "token": "x", "nested": []any{map[string]any{"reason": "literal-private", "authorization": "Bearer x"}}}
	clean, err := Redact(value, []string{"literal-private"})
	if err != nil {
		t.Fatal(err)
	}
	object := clean.(map[string]any)
	if object["password"] != Redacted || object["prompt_tokens"] != 12 || object["output_tokens"] != 7 {
		t.Fatal("redaction erased metrics")
	}
	raw, _ := json.Marshal(clean)
	if bytes.Contains(raw, []byte("literal-private")) {
		t.Fatal("literal leak")
	}
	for _, text := range []string{"Bearer opaque", "password=unknown", "postgresql://user:pass@db/name", "api_key = unknown"} {
		clean, err := Redact(text, nil)
		if err != nil || clean != Redacted {
			t.Fatal("credential text leak")
		}
	}
	writer, path := makeWriter(t, Options{Secrets: []string{"literal-private"}})
	if err := writer.Emit(failure("literal-private")); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	raw, _ = os.ReadFile(path)
	if bytes.Contains(raw, []byte("literal-private")) {
		t.Fatal("file leaked secret")
	}
}
func TestInvalidDataAndSemanticGate(t *testing.T) {
	cases := []Record{}
	invalidDuration := end()
	invalidDuration.Data["duration_ms"] = -1
	cases = append(cases, invalidDuration)
	invalidCounts := end()
	invalidCounts.Data["prompt_tokens"] = nil
	cases = append(cases, invalidCounts)
	cases = append(cases, Record{Type: "tool.started", Phase: "execution", Status: "ok", CallID: "call-one", Data: map[string]any{"tool_id": "billing_list_items", "arguments": map[string]any{"customer_id": "CUST-001"}, "retry_index": 0}})
	for _, invalid := range []any{math.NaN(), math.Inf(1), make(chan int), string([]byte{0xff})} {
		event := start()
		event.Data["extra"] = invalid
		cases = append(cases, event)
	}
	for i, event := range cases {
		t.Run(string(rune('a'+i)), func(t *testing.T) {
			writer, _ := makeWriter(t, Options{})
			if err := writer.Emit(event); err == nil {
				t.Fatal("accepted invalid event")
			}
			if writer.Summary().Events != 0 {
				t.Fatal("invalid bytes accepted")
			}
			if err := writer.Close(); err == nil {
				t.Fatal("invalid trace complete")
			}
		})
	}
}
func TestCorrelationAndOperationReuse(t *testing.T) {
	for _, change := range []string{"missing", "parent", "identity", "reuse"} {
		t.Run(change, func(t *testing.T) {
			writer, _ := makeWriter(t, Options{})
			if change != "missing" {
				if err := writer.Emit(start()); err != nil {
					t.Fatal(err)
				}
			}
			event := end()
			if change == "parent" {
				event.ParentCallID = "parent-other"
			}
			if change == "identity" {
				event.Data["model_digest"] = strings.Repeat("b", 64)
			}
			if change == "reuse" {
				if err := writer.Emit(end()); err != nil {
					t.Fatal(err)
				}
				event = start()
			}
			if err := writer.Emit(event); err == nil {
				t.Fatal("accepted invalid correlation")
			}
			if err := writer.Close(); err == nil {
				t.Fatal("complete after invalid correlation")
			}
		})
	}
}
func TestCapsAndClockRegression(t *testing.T) {
	for _, options := range []Options{{MaxLine: 10}, {MaxBytes: 10}, {MaxEvents: 1}} {
		writer, _ := makeWriter(t, options)
		if options.MaxEvents == 1 {
			if err := writer.Emit(start()); err != nil {
				t.Fatal(err)
			}
		}
		if err := writer.Emit(failure("safe category")); err != LogError("capacity") {
			t.Fatal(err)
		}
		if err := writer.Close(); err == nil {
			t.Fatal("cap failure hidden")
		}
	}
	now := time.Date(2026, 11, 8, 19, 0, 0, 0, time.UTC)
	writer, _ := makeWriter(t, Options{Now: func() time.Time { return now }})
	now = now.Add(-time.Millisecond)
	if err := writer.Emit(start()); err != LogError("clock") {
		t.Fatal(err)
	}
}
func TestEmptyUnclosedAndPostClose(t *testing.T) {
	writer, _ := makeWriter(t, Options{})
	if err := writer.Close(); err != LogError("empty") {
		t.Fatal(err)
	}
	writer, _ = makeWriter(t, Options{})
	if err := writer.Emit(start()); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != LogError("unclosed_operation") {
		t.Fatal(err)
	}
	writer, _ = makeWriter(t, Options{})
	if err := writer.Emit(failure("safe category")); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	if err := writer.Emit(failure("safe category")); err != LogError("closed") {
		t.Fatal(err)
	}
	if writer.Summary().ArtifactComplete {
		t.Fatal("misuse hidden")
	}
}

type faultFile struct {
	real  durableFile
	fault string
}

func (f faultFile) Write(p []byte) (int, error) {
	if f.fault == "write" {
		return 0, errors.New("private I/O error")
	}
	if f.fault == "short" {
		return 0, nil
	}
	return f.real.Write(p)
}
func (f faultFile) Sync() error {
	if f.fault == "sync" {
		return errors.New("private sync error")
	}
	return f.real.Sync()
}
func (f faultFile) Close() error {
	err := f.real.Close()
	if f.fault == "close" {
		return errors.New("private close error")
	}
	return err
}
func TestIOFailuresAndSanitizedErrors(t *testing.T) {
	for _, fault := range []string{"write", "short", "sync", "close"} {
		t.Run(fault, func(t *testing.T) {
			writer, _ := makeWriter(t, Options{})
			writer.file = faultFile{writer.file, fault}
			err := writer.Emit(failure("safe category"))
			if fault != "close" && err == nil {
				t.Fatal("I/O failure suppressed")
			}
			if err != nil && strings.Contains(err.Error(), "private") {
				t.Fatal("raw error exposed")
			}
			if err := writer.Close(); err == nil {
				t.Fatal("close suppressed failure")
			}
			if writer.Summary().ArtifactComplete {
				t.Fatal("broken output complete")
			}
		})
	}
}
func TestExclusiveNoSymlinkAndMetadataSecrets(t *testing.T) {
	writer, path := makeWriter(t, Options{})
	_, err := New(path, Context{"run-test", "attempt-test", "agent"}, Options{Validate: contract(t)})
	if err != LogError("open") {
		t.Fatal(err)
	}
	_ = writer.Close()
	link := filepath.Join(t.TempDir(), "link")
	if err := os.Symlink(path, link); err != nil {
		t.Fatal(err)
	}
	_, err = New(link, Context{"run-test", "attempt-test", "agent"}, Options{Validate: contract(t)})
	if err != LogError("open") {
		t.Fatal(err)
	}
	writer, _ = makeWriter(t, Options{Secrets: []string{"call-one"}})
	if err := writer.Emit(start()); err != LogError("metadata_secret") {
		t.Fatal(err)
	}
}

func TestAddSecretsCopiesAndRedactsWithoutReset(t *testing.T) {
	w, path := makeWriter(t, Options{})
	if err := w.Emit(failure("initial failure")); err != nil {
		t.Fatal(err)
	}
	secrets := []string{"new-private-literal"}
	if err := w.AddSecrets(secrets); err != nil {
		t.Fatal(err)
	}
	secrets[0] = "changed-by-caller"
	if err := w.AddSecrets([]string{"valid-before-invalid", ""}); err == nil {
		t.Fatal("invalid secret admitted")
	}
	if len(w.options.Secrets) != 1 {
		t.Fatal("partial update or caller alias")
	}
	if err := w.Emit(failure("new-private-literal")); err != nil {
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	events := readEvents(t, path)
	if events[1]["sequence"] != float64(2) || events[1]["data"].(map[string]any)["failure"].(map[string]any)["reason"] != Redacted {
		t.Fatal("new secret not redacted or sequence reset", events)
	}
	if err := w.AddSecrets([]string{"later"}); err == nil {
		t.Fatal("closed writer updated")
	}
}
func TestAddSecretsRejectsFailedAndInvalidUTF8(t *testing.T) {
	w, _ := makeWriter(t, Options{})
	if err := w.AddSecrets([]string{string([]byte{0xff})}); err == nil {
		t.Fatal("invalid UTF8 admitted")
	}
	w.failure = "write"
	if err := w.AddSecrets([]string{"new-private-literal"}); err == nil || len(w.options.Secrets) != 0 {
		t.Fatal("failed writer updated")
	}
}
