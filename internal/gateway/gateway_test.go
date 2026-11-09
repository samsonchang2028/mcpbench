package gateway

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
	"mcpbench/internal/billing"
	billingmcp "mcpbench/internal/mcp"
)

type roundFunc func(*http.Request) (*http.Response, error)

func (f roundFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }
func request(method, path string, body io.Reader) *http.Request {
	r := httptest.NewRequest(method, "http://127.0.0.1:18081"+path, body)
	return r
}
func TestBoundsAndFixedDestination(t *testing.T) {
	calls := 0
	h := newHandler(roundFunc(func(r *http.Request) (*http.Response, error) {
		calls++
		if r.URL.String() != upstream+"/mcp" || r.Host != "127.0.0.1:18081" || r.Header.Get("Authorization") != "Bearer synthetic" || r.Header.Get("Origin") != "http://localhost:18081" {
			t.Fatal("routing or headers")
		}
		return &http.Response{StatusCode: 307, Header: http.Header{"Location": []string{"http://elsewhere.invalid/"}}, Body: io.NopCloser(strings.NewReader("redirect"))}, nil
	}))
	r := request("POST", "/mcp", strings.NewReader("{}"))
	r.Header.Set("Authorization", "Bearer synthetic")
	r.Header.Set("Origin", "http://localhost:18081")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 307 || calls != 1 {
		t.Fatal(w.Code, calls)
	}
	for _, c := range []struct {
		method, path, host, origin string
		body                       int
		code                       int
	}{
		{"POST", "/other", "", "", 0, 404}, {"POST", "/mcp?url=x", "", "", 0, 404},
		{"PUT", "/mcp", "", "", 0, 405}, {"POST", "/healthz", "", "", 0, 405},
		{"POST", "/mcp", "evil.invalid", "", 0, 403}, {"POST", "/mcp", "", "http://evil.invalid", 0, 403},
		{"POST", "/mcp", "", "", MaxBody + 1, 413},
	} {
		r := request(c.method, c.path, bytes.NewReader(make([]byte, c.body)))
		if c.host != "" {
			r.Host = c.host
		}
		if c.origin != "" {
			r.Header.Set("Origin", c.origin)
		}
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != c.code {
			t.Fatalf("%+v got %d", c, w.Code)
		}
	}
	if calls != 1 {
		t.Fatal("invalid request reached upstream")
	}
	r = request("POST", "/mcp", nil)
	r.Header.Set("Authorization", strings.Repeat("x", MaxHeader))
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 431 {
		t.Fatal(w.Code)
	}
}
func TestResponseBoundAndCancellation(t *testing.T) {
	h := newHandler(roundFunc(func(r *http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(strings.Repeat("x", MaxBody+1)))}, nil
	}))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, request("POST", "/mcp", nil))
	if w.Code != 502 {
		t.Fatal(w.Code)
	}
	h = newHandler(roundFunc(func(r *http.Request) (*http.Response, error) { <-r.Context().Done(); return nil, r.Context().Err() }))
	r := request("POST", "/mcp", nil)
	ctx, cancel := context.WithCancel(r.Context())
	cancel()
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r.WithContext(ctx))
	if w.Code != 502 {
		t.Fatal(w.Code)
	}
}
func TestConcurrencyBound(t *testing.T) {
	entered := make(chan struct{}, 4)
	release := make(chan struct{})
	done := make(chan struct{}, 4)
	h := newHandler(roundFunc(func(r *http.Request) (*http.Response, error) {
		entered <- struct{}{}
		<-release
		return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader("ok"))}, nil
	}))
	for i := 0; i < 4; i++ {
		go func() { h.ServeHTTP(httptest.NewRecorder(), request("GET", "/mcp", nil)); done <- struct{}{} }()
	}
	for i := 0; i < 4; i++ {
		<-entered
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, request("GET", "/mcp", nil))
	if w.Code != 503 {
		t.Fatal(w.Code)
	}
	close(release)
	for i := 0; i < 4; i++ {
		<-done
	}
}

// Loopback sockets exercise the real pinned SDK on both sides of the gateway.
type service struct {
	denied atomic.Bool
	calls  atomic.Int32
}

func (s *service) Authorize(context.Context, billing.Access) ([]string, error) {
	if s.denied.Load() {
		return nil, billing.Fail("authorization_denied")
	}
	return []string{"billing_list_customers"}, nil
}
func (s *service) Call(context.Context, billing.Access, string, json.RawMessage) (any, error) {
	s.calls.Add(1)
	return billing.CustomerOutput{Customers: []billing.Customer{{ID: "CUST-001", Name: "Example Studio", Active: true}}}, nil
}
func TestOfficialSDKThroughGateway(t *testing.T) {
	svc := &service{}
	handler, e := billingmcp.New(billingmcp.Options{Service: svc, Ready: func(context.Context) error { return nil }})
	if e != nil {
		t.Fatal(e)
	}
	backend := httptest.NewServer(handler)
	defer backend.Close()
	dest, _ := url.Parse(backend.URL)
	raw := &http.Transport{Proxy: nil, DisableKeepAlives: true}
	defer raw.CloseIdleConnections()
	front := httptest.NewServer(newHandler(roundFunc(func(r *http.Request) (*http.Response, error) {
		r = r.Clone(r.Context())
		u := *r.URL
		u.Host = dest.Host
		r.URL = &u
		return raw.RoundTrip(r)
	})))
	defer front.Close()
	client := &http.Client{Timeout: 3 * time.Second, Transport: roundFunc(func(r *http.Request) (*http.Response, error) {
		r = r.Clone(r.Context())
		r.Host = "127.0.0.1:18081"
		r.Header = r.Header.Clone()
		r.Header.Set("Origin", "http://127.0.0.1:18081")
		r.Header.Set("Authorization", "Bearer "+strings.Repeat("a", 64))
		r.Header.Set("X-MCPBench-Run-ID", "run-test")
		r.Header.Set("X-MCPBench-Attempt-ID", "attempt-test")
		r.Header.Set("X-MCPBench-Idempotency-Key", "key-test")
		return http.DefaultTransport.RoundTrip(r)
	})}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	session, e := sdk.NewClient(&sdk.Implementation{Name: "gateway-test", Version: "1"}, nil).Connect(ctx, &sdk.StreamableClientTransport{Endpoint: front.URL + "/mcp", HTTPClient: client}, nil)
	if e != nil {
		t.Fatal(e)
	}
	defer session.Close()
	listed, e := session.ListTools(ctx, nil)
	if e != nil || len(listed.Tools) != 1 {
		t.Fatal(listed, e)
	}
	result, e := session.CallTool(ctx, &sdk.CallToolParams{Name: "billing_list_customers", Arguments: map[string]any{}})
	if e != nil || result.IsError || result.StructuredContent == nil {
		t.Fatal(result, e)
	}
	svc.denied.Store(true)
	_, e = session.CallTool(ctx, &sdk.CallToolParams{Name: "billing_list_customers", Arguments: map[string]any{}})
	if e == nil || svc.calls.Load() != 1 {
		t.Fatal("revocation did not reach upstream", e)
	}
}
