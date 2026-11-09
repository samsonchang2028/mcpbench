package mcp

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"sync"
	"testing"
	"time"

	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
	"mcpbench/internal/billing"
	"mcpbench/observability"
)

const token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

type fakeService struct {
	mu           sync.Mutex
	revoked      bool
	acl          []string
	auths, calls int
	seen         billing.Access
	value        any
	err          error
}

func (f *fakeService) Authorize(ctx context.Context, a billing.Access) ([]string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.auths++
	f.seen = a
	if f.revoked {
		return nil, billing.Fail("authorization_denied")
	}
	return append([]string(nil), f.acl...), nil
}
func (f *fakeService) Call(ctx context.Context, a billing.Access, name string, args json.RawMessage) (any, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls++
	f.seen = a
	if f.revoked {
		return nil, billing.Fail("authorization_denied")
	}
	allowed := false
	for _, v := range f.acl {
		allowed = allowed || v == name
	}
	if !allowed {
		return nil, billing.Fail("authorization_denied")
	}
	if f.err != nil {
		return nil, f.err
	}
	if f.value != nil {
		return f.value, nil
	}
	return billing.CustomerOutput{Customers: []billing.Customer{{ID: "CUST-001", Name: "Example Studio", Active: true}}}, nil
}
func headers(h http.Header) {
	h.Set("Authorization", "Bearer "+token)
	h.Set("X-MCPBench-Run-ID", "run-test")
	h.Set("X-MCPBench-Attempt-ID", "attempt-test")
	h.Set("X-MCPBench-Idempotency-Key", "key-test")
}

type wire struct {
	base              http.RoundTripper
	mu                sync.Mutex
	methods, versions []string
}

func (w *wire) RoundTrip(r *http.Request) (*http.Response, error) {
	r = r.Clone(r.Context())
	r.Header = r.Header.Clone()
	r.Host = "127.0.0.1:18081"
	headers(r.Header)
	if r.Body != nil {
		b, _ := io.ReadAll(r.Body)
		r.Body.Close()
		r.Body = io.NopCloser(bytes.NewReader(b))
		var msg struct {
			Method string `json:"method"`
		}
		json.Unmarshal(b, &msg)
		w.mu.Lock()
		w.methods = append(w.methods, msg.Method)
		w.versions = append(w.versions, r.Header.Get("MCP-Protocol-Version"))
		w.mu.Unlock()
	}
	return w.base.RoundTrip(r)
}
func newFixture(t *testing.T, f *fakeService, o Options) (*httptest.Server, *sdk.ClientSession, *wire) {
	t.Helper()
	o.Service = f
	if o.Ready == nil {
		o.Ready = func(context.Context) error { return nil }
	}
	h, err := New(o)
	if err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	w := &wire{base: http.DefaultTransport}
	c := sdk.NewClient(&sdk.Implementation{Name: "test", Version: "1"}, &sdk.ClientOptions{Capabilities: &sdk.ClientCapabilities{}})
	session, err := c.Connect(context.Background(), &sdk.StreamableClientTransport{Endpoint: srv.URL + "/mcp", HTTPClient: &http.Client{Transport: w}, MaxRetries: -1, DisableStandaloneSSE: true}, nil)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { session.Close() })
	return srv, session, w
}

func TestSDKDiscoverySchemasCallAndRevocation(t *testing.T) {
	f := &fakeService{acl: []string{billing.ListCustomers, billing.ListItems, billing.CreateDraft}}
	_, session, w := newFixture(t, f, Options{})
	list, err := session.ListTools(context.Background(), &sdk.ListToolsParams{})
	if err != nil {
		t.Fatal(err)
	}
	if len(list.Tools) != 3 || list.NextCursor != "" {
		t.Fatalf("catalog: %#v", list)
	}
	var catalog struct{ Tools []catalogEntry }
	json.Unmarshal(catalogBytes, &catalog)
	for i, tool := range list.Tools {
		var entry catalogEntry
		for _, e := range catalog.Tools {
			if e.Name == tool.Name {
				entry = e
			}
		}
		if entry.Name == "" {
			t.Fatal("unknown tool", i)
		}
		in, _ := resolved(entry.InputRef)
		out, _ := resolved(entry.OutputRef)
		raw, _ := json.Marshal(tool.InputSchema)
		var actual map[string]any
		json.Unmarshal(raw, &actual)
		if !reflect.DeepEqual(actual, in) {
			t.Fatal("input schema mismatch")
		}
		raw, _ = json.Marshal(tool.OutputSchema)
		json.Unmarshal(raw, &actual)
		if !reflect.DeepEqual(actual, out) {
			t.Fatal("output schema mismatch")
		}
		if bytes.Contains(raw, []byte(`"$ref"`)) {
			t.Fatal("unresolved schema")
		}
	}
	result, err := session.CallTool(context.Background(), &sdk.CallToolParams{Name: billing.ListCustomers, Arguments: json.RawMessage(`{}`)})
	if err != nil || result.IsError {
		t.Fatalf("call: %v %#v", err, result)
	}
	raw, _ := json.Marshal(result.StructuredContent)
	if validate("ListCustomerOutput", raw) != nil {
		t.Fatalf("business output %s", raw)
	}
	f.mu.Lock()
	a := f.seen
	auths := f.auths
	f.revoked = true
	f.mu.Unlock()
	if a.Capability != token || a.RunID != "run-test" || a.IdempotencyKey != "key-test" || auths < 3 {
		t.Fatal("private identity/auth missing")
	}
	if _, err = session.ListTools(context.Background(), &sdk.ListToolsParams{}); err == nil {
		t.Fatal("cached auth after revocation")
	}
	w.mu.Lock()
	defer w.mu.Unlock()
	if len(w.methods) == 0 || w.methods[0] != "server/discover" {
		t.Fatalf("no real discovery: %v", w.methods)
	}
	found := false
	for _, v := range w.versions {
		found = found || v == ProtocolVersion
	}
	if !found {
		t.Fatalf("protocol not selected: %v", w.versions)
	}
}
func TestSDKACLArgumentsErrorsAndUnknown(t *testing.T) {
	f := &fakeService{acl: []string{billing.ListCustomers}}
	_, s, _ := newFixture(t, f, Options{})
	l, e := s.ListTools(context.Background(), &sdk.ListToolsParams{})
	if e != nil || len(l.Tools) != 1 || l.Tools[0].Name != billing.ListCustomers {
		t.Fatal("ACL", e, l)
	}
	for _, tc := range []struct{ name, args, code string }{{billing.ListCustomers, `{"unknown":1}`, "invalid_arguments"}, {billing.ListItems, `{}`, "authorization_denied"}} {
		r, e := s.CallTool(context.Background(), &sdk.CallToolParams{Name: tc.name, Arguments: json.RawMessage(tc.args)})
		if e != nil || !r.IsError {
			t.Fatalf("failure: %v %#v", e, r)
		}
		b, _ := json.Marshal(r.StructuredContent)
		var bounded billing.Error
		json.Unmarshal(b, &bounded)
		if validate("ToolError", b) != nil || bounded.Code != tc.code {
			t.Fatalf("wrong direct error %s", b)
		}
	}
	if _, e = s.CallTool(context.Background(), &sdk.CallToolParams{Name: "arbitrary_shell", Arguments: json.RawMessage(`{}`)}); e == nil {
		t.Fatal("unknown direct tool did not produce protocol error")
	}
	f.mu.Lock()
	f.value = map[string]any{"wrong": "shape"}
	f.mu.Unlock()
	r, e := s.CallTool(context.Background(), &sdk.CallToolParams{Name: billing.ListCustomers, Arguments: json.RawMessage(`{}`)})
	if e != nil || !r.IsError {
		t.Fatal("invalid server output admitted", e)
	}
}
func TestSDKUnknownCommitAndSanitizedError(t *testing.T) {
	f := &fakeService{acl: []string{billing.ListCustomers}, err: &billing.Error{Code: "db_error", Message: "password=" + token, OutcomeUnknown: true}}
	unknown := false
	_, s, _ := newFixture(t, f, Options{Diagnostic: func(run, attempt string, b bool) { unknown = b }})
	r, e := s.CallTool(context.Background(), &sdk.CallToolParams{Name: billing.ListCustomers, Arguments: json.RawMessage(`{}`)})
	b, _ := json.Marshal(r)
	if e != nil || !r.IsError || !unknown || bytes.Contains(b, []byte(token)) || bytes.Contains(b, []byte("OutcomeUnknown")) {
		t.Fatalf("private evidence/error: %s %v", b, e)
	}
}
func TestHTTPGuardsAndReadiness(t *testing.T) {
	f := &fakeService{acl: []string{billing.ListCustomers}}
	h, e := New(Options{Service: f, Ready: func(context.Context) error { return errors.New("private diagnostic") }})
	if e != nil {
		t.Fatal(e)
	}
	for _, tc := range []struct {
		name, host, origin, body string
		status                   int
	}{
		{"bad-host", "evil.example", "", `{}`, 403}, {"bad-origin", "127.0.0.1:18081", "https://evil.example", `{}`, 403},
		{"duplicate", "127.0.0.1:18081", "", `{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{},"params":{}}`, 400},
		{"invalid-utf8", "127.0.0.1:18081", "", string([]byte{'{', '"', 0xff, '"', ':', '1', '}'}), 400},
		{"oversize", "127.0.0.1:18081", "", strings.Repeat(" ", MaxBody+1), 413},
	} {
		t.Run(tc.name, func(t *testing.T) {
			r := httptest.NewRequest("POST", "http://127.0.0.1:18081/mcp", strings.NewReader(tc.body))
			r.Host = tc.host
			headers(r.Header)
			r.Header.Set("Content-Type", "application/json")
			r.Header.Set("Accept", "application/json, text/event-stream")
			if tc.origin != "" {
				r.Header.Set("Origin", tc.origin)
			}
			w := httptest.NewRecorder()
			h.ServeHTTP(w, r)
			if w.Code != tc.status {
				t.Fatalf("%d %s", w.Code, w.Body.String())
			}
		})
	}
	for _, path := range []string{"/mcp", "/healthz"} {
		r := httptest.NewRequest("GET", "http://localhost:18081"+path, nil)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		want := 401
		if path == "/healthz" {
			want = 503
		}
		if w.Code != want || strings.Contains(w.Body.String(), "private") {
			t.Fatal(w.Code, w.Body.String())
		}
	}
	r := httptest.NewRequest("POST", "http://localhost:18081/mcp", strings.NewReader(`{}`))
	headers(r.Header)
	r.Header.Add("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 401 {
		t.Fatal("duplicate auth admitted")
	}
}
func TestRealWriterEvents(t *testing.T) {
	path := filepath.Join(t.TempDir(), "events.jsonl")
	writer, e := observability.New(path, observability.Context{RunID: "run-test", AttemptID: "attempt-test", Source: "mcp"}, observability.Options{Validate: func(e map[string]any) error {
		err := ValidateEvent(e)
		if err != nil {
			b, _ := json.Marshal(e)
			t.Logf("bad event %s", b)
		}
		return err
	}, Secrets: []string{token}})
	if e != nil {
		t.Fatal(e)
	}
	f := &fakeService{acl: []string{billing.ListCustomers}}
	_, s, _ := newFixture(t, f, Options{Events: func(run, attempt string) (*observability.Writer, string, error) { return writer, "execution", nil }})
	r, e := s.CallTool(context.Background(), &sdk.CallToolParams{Name: billing.ListCustomers, Arguments: json.RawMessage(`{}`)})
	if e != nil || r.IsError {
		t.Fatal("success event", e, r)
	}
	f.mu.Lock()
	f.err = billing.Fail("not_found")
	f.mu.Unlock()
	r, e = s.CallTool(context.Background(), &sdk.CallToolParams{Name: billing.ListCustomers, Arguments: json.RawMessage(`{}`)})
	if e != nil || !r.IsError {
		t.Fatal("failure event", e, r)
	}
	if e = writer.Close(); e != nil {
		t.Fatal(e)
	}
	if !writer.Summary().ArtifactComplete {
		t.Fatal(writer.Summary())
	}
	b, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	if bytes.Contains(b, []byte(token)) {
		t.Fatal("secret in events")
	}
	parityTrace(t, b)
	lines := bytes.Split(bytes.TrimSpace(b), []byte("\n"))
	if len(lines) != 4 {
		t.Fatalf("events %s", b)
	}
	for _, line := range lines {
		var event map[string]any
		json.Unmarshal(line, &event)
		if ValidateEvent(event) != nil {
			t.Fatal("invalid emitted event", string(line))
		}
	}
	// Genuine validator rejects semantically contradictory nested arguments.
	var event map[string]any
	json.Unmarshal(lines[0], &event)
	event["data"].(map[string]any)["arguments"] = map[string]any{"customer_id": "CUST-001"}
	if ValidateEvent(event) == nil {
		t.Fatal("shape-only event validator")
	}
}

func parityTrace(t *testing.T, b []byte) {
	t.Helper()
	python := os.Getenv("MCPBENCH_TEST_PYTHON")
	if python == "" {
		t.Fatal("MCPBENCH_TEST_PYTHON required for frozen validator parity")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, python, "-c", `import sys
from contracts.validate import load_bytes,validate,validate_event_stream
es=[load_bytes(x) for x in sys.stdin.buffer if x.strip()]
for e in es: validate("Event",e)
validate_event_stream(es)
`)
	cmd.Dir = "../.."
	cmd.Stdin = bytes.NewReader(b)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("event parity: %v %s", err, out)
	}
}
func TestEmbeddedContractIdentity(t *testing.T) {
	for _, tc := range []struct {
		path     string
		embedded []byte
	}{{"schema.json", schemaBytes}, {"catalog.json", catalogBytes}} {
		raw, err := os.ReadFile(filepath.Join("../../contracts/v1", tc.path))
		if err != nil || !bytes.Equal(raw, tc.embedded) {
			t.Fatal("embedded contract drift", tc.path, err)
		}
	}
}
func TestSourceBoundedAcquisition(t *testing.T) {
	source := &Source{slots: make(chan struct{}, 5)}
	for range 5 {
		source.slots <- struct{}{}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, _, err := source.connect(ctx); !errors.Is(err, context.Canceled) {
		t.Fatal("acquisition escaped cancellation", err)
	}
	if len(source.slots) != 5 {
		t.Fatal("acquisition leaked slot")
	}
}
func TestResponseBufferBound(t *testing.T) {
	b := &responseBuffer{header: make(http.Header)}
	if _, e := b.Write(make([]byte, MaxBody)); e != nil {
		t.Fatal(e)
	}
	if _, e := b.Write([]byte{1}); e == nil || !b.overflow {
		t.Fatal("response overflow admitted")
	}
}
func TestDedicatedEnvironmentRejectsOverrides(t *testing.T) {
	for _, k := range []string{"PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGOPTIONS", "PGPASSFILE"} {
		t.Run(k, func(t *testing.T) {
			t.Setenv(k, "untrusted")
			if _, err := ServiceSource(); err == nil {
				t.Fatal("inherited override admitted")
			}
		})
	}
}

func TestSDKItemsAndDraftBusinessResults(t *testing.T) {
	raw, err := os.ReadFile("../../contracts/v1/verifier-result.example.json")
	if err != nil {
		t.Fatal(err)
	}
	var sample struct {
		Checks []struct {
			ToolResult struct {
				Result any `json:"result"`
			} `json:"tool_result"`
		} `json:"checks"`
	}
	if json.Unmarshal(raw, &sample) != nil || len(sample.Checks) < 1 {
		t.Fatal("fixture")
	}
	args := json.RawMessage(`{"customer_id":"CUST-001","invoice_date":"2026-11-07","due_date":"2026-11-21","lines":[{"item_id":"SVC-CONSULT","quantity":2}]}`)
	for _, tc := range []struct {
		name, kind string
		args       json.RawMessage
		value      any
	}{
		{billing.ListItems, "ListItemOutput", json.RawMessage(`{}`), billing.ItemOutput{Items: []billing.Item{{ID: "SVC-CONSULT", Name: "Consulting", Unit: "hour", Currency: "USD", Price: 12500, Active: true}}}},
		{billing.CreateDraft, "DraftOutput", args, sample.Checks[0].ToolResult.Result},
	} {
		t.Run(tc.name, func(t *testing.T) {
			f := &fakeService{acl: []string{tc.name}, value: tc.value}
			_, session, _ := newFixture(t, f, Options{})
			r, err := session.CallTool(context.Background(), &sdk.CallToolParams{Name: tc.name, Arguments: tc.args})
			if err != nil || r.IsError {
				t.Fatalf("call %v %#v", err, r)
			}
			b, _ := json.Marshal(r.StructuredContent)
			if validate(tc.kind, b) != nil {
				t.Fatalf("business schema %s", b)
			}
		})
	}
}
