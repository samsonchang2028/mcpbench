package agent

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

type fakeHTTP func(*http.Request) (*http.Response, error)

func (f fakeHTTP) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }
func TestSDKNegotiationAndAuthBoundary(t *testing.T) {
	_, a, w, _ := fixture(t)
	w.Close()
	calls := []string{}
	transport := fakeHTTP(func(r *http.Request) (*http.Response, error) {
		if r.URL.String() != MCPEndpoint || r.Header.Get("Authorization") != "Bearer "+a.Capability || r.Header.Get("X-MCPBench-Idempotency-Key") != a.IdempotencyKey || r.Header.Get("X-MCPBench-Run-ID") != a.RunID || r.Header.Get("X-MCPBench-Attempt-ID") != a.AttemptID {
			t.Fatal("missing trusted headers")
		}
		var q map[string]any
		if json.NewDecoder(r.Body).Decode(&q) != nil {
			t.Fatal("bad JSONRPC")
		}
		method := q["method"].(string)
		calls = append(calls, method)
		var result any
		switch method {
		case "server/discover":
			result = map[string]any{"supportedVersions": []string{"2026-07-28"}, "capabilities": map[string]any{"tools": map[string]any{}}}
		case "notifications/initialized":
			return &http.Response{StatusCode: 204, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(""))}, nil
		case "tools/list":
			result = map[string]any{"tools": []any{map[string]any{"name": "billing_list_customers", "inputSchema": map[string]any{"type": "object"}}}}
		case "tools/call":
			result = map[string]any{"content": []any{}, "structuredContent": map[string]any{"customers": []any{}}, "isError": false}
		default:
			t.Fatalf("unexpected method %s", method)
		}
		b, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": q["id"], "result": result})
		h := make(http.Header)
		h.Set("Content-Type", "application/json")
		return &http.Response{StatusCode: 200, Header: h, Body: io.NopCloser(strings.NewReader(string(b)))}, nil
	})
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	c, e := connectMCP(ctx, a, transport)
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	list, e := c.List(ctx)
	if e != nil || len(list) != 1 {
		t.Fatalf("%v %v", list, e)
	}
	r, e := c.Call(ctx, "billing_list_customers", json.RawMessage(`{}`))
	if e != nil || r.IsError {
		t.Fatalf("%+v %v", r, e)
	}
	if len(calls) != 3 {
		t.Fatal(calls)
	}
}
func TestMCPRejectsRawDuplicatesAndSSE(t *testing.T) {
	for _, tc := range []struct{ content, body string }{{"application/json", `{"jsonrpc":"2.0","id":1,"id":2}`}, {"text/event-stream", "data: {}\n\n"}} {
		tr := authTransport{auth: AuthInput{}, base: fakeHTTP(func(*http.Request) (*http.Response, error) {
			h := make(http.Header)
			h.Set("Content-Type", tc.content)
			return &http.Response{StatusCode: 200, Header: h, Body: io.NopCloser(strings.NewReader(tc.body))}, nil
		})}
		q, _ := http.NewRequest("POST", MCPEndpoint, strings.NewReader(`{}`))
		if _, e := tr.RoundTrip(q); e == nil {
			t.Fatal("accepted invalid wire")
		}
	}
}

func TestNormalizeMCPBusinessAndErrorResults(t *testing.T) {
	for _, tc := range []struct {
		name    string
		isError bool
		body    string
		valid   bool
	}{
		{"billing_list_customers", false, `{"customers":[]}`, true},
		{"billing_list_items", false, `{"customers":[]}`, false},
		{"billing_list_items", true, `{"code":"authorization_denied","message":"Denied.","retryable":false}`, true},
		{"billing_list_items", true, `{"code":"authorization_denied","message":"Denied.","retryable":true}`, false},
		{"billing_list_customers", false, `{"tool_id":"billing_list_customers","is_error":false,"result":{"customers":[]}}`, false},
		{"billing_list_customers", false, `{"customers":[],"customers":[]}`, false},
	} {
		r, e := normalizeMCPResult(tc.name, tc.isError, []byte(tc.body), nil)
		if (e == nil) != tc.valid || e == nil && (r.ToolID != tc.name || r.IsError != tc.isError) {
			t.Fatalf("%+v => %+v %v", tc, r, e)
		}
	}
}
