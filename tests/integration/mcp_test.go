// These opt-in checks require an operator-admitted, independently prepared owned
// run. Default execution skips before reading auth or contacting any endpoint.
package integration_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"sync"
	"testing"
	"time"

	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
	"mcpbench/internal/agent"
	"mcpbench/internal/billing"
)

var args = json.RawMessage(`{"customer_id":"CUST-001","invoice_date":"2026-11-07","due_date":"2026-11-21","lines":[{"item_id":"SVC-CONSULT","quantity":2}]}`)

type timeout struct{}

func (timeout) Error() string   { return "injected response timeout" }
func (timeout) Timeout() bool   { return true }
func (timeout) Temporary() bool { return true }

type wire struct {
	auth   agent.AuthInput
	base   http.RoundTripper
	mu     sync.Mutex
	drop   bool
	lostID string
}

func (w *wire) RoundTrip(request *http.Request) (*http.Response, error) {
	if request.URL.Scheme != "http" || request.URL.Host != "127.0.0.1:18081" || request.URL.Path != "/mcp" {
		return nil, errors.New("fixed endpoint")
	}
	request = request.Clone(request.Context())
	request.Header = request.Header.Clone()
	request.Header.Set("Authorization", "Bearer "+w.auth.Capability)
	request.Header.Set("X-MCPBench-Run-ID", w.auth.RunID)
	request.Header.Set("X-MCPBench-Attempt-ID", w.auth.AttemptID)
	request.Header.Set("X-MCPBench-Idempotency-Key", w.auth.IdempotencyKey)
	var message struct {
		Method string `json:"method"`
		Params struct {
			Name string `json:"name"`
		} `json:"params"`
	}
	if request.Body != nil {
		raw, e := io.ReadAll(io.LimitReader(request.Body, 1048577))
		request.Body.Close()
		if e != nil || len(raw) > 1048576 {
			return nil, errors.New("request limit")
		}
		request.Body = io.NopCloser(bytes.NewReader(raw))
		json.Unmarshal(raw, &message)
	}
	response, err := w.base.RoundTrip(request)
	if err != nil {
		return nil, err
	}
	if message.Method == "tools/call" && message.Params.Name == billing.CreateDraft {
		w.mu.Lock()
		defer w.mu.Unlock()
		if w.drop {
			raw, e := io.ReadAll(io.LimitReader(response.Body, 1048577))
			response.Body.Close()
			if e != nil || len(raw) > 1048576 {
				return nil, errors.New("response limit")
			}
			var rpc struct {
				Result struct {
					IsError bool                `json:"isError"`
					Value   billing.DraftOutput `json:"structuredContent"`
				} `json:"result"`
			}
			if json.Unmarshal(raw, &rpc) != nil || rpc.Result.IsError || rpc.Result.Value.Invoice.ID == "" {
				return nil, errors.New("no committed response to discard")
			}
			w.drop = false
			w.lostID = rpc.Result.Value.Invoice.ID
			// The actual SDK server has returned a positively acknowledged business
			// result. Discard exactly this response and inject a client read timeout.
			return nil, timeout{}
		}
	}
	return response, nil
}
func connect(t *testing.T, drop bool) (*sdk.ClientSession, *wire) {
	t.Helper()
	if os.Getenv("MCPBENCH_INTEGRATION_LIVE") != "yes" {
		t.Skip("UNRUN: explicit root-owned PostgreSQL/MCP admission required")
	}
	raw, err := agent.ReadDocument(os.Getenv("MCPBENCH_INTEGRATION_AUTH"))
	if err != nil {
		t.Fatal("private auth unavailable")
	}
	var auth agent.AuthInput
	if agent.Decode("AuthInput", raw, &auth) != nil || auth.Mode != "agent" {
		t.Fatal("invalid execution auth")
	}
	w := &wire{auth: auth, base: &http.Transport{Proxy: nil}, drop: drop}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	session, err := sdk.NewClient(&sdk.Implementation{Name: "mcpbench-admitted-regression", Version: "1"}, &sdk.ClientOptions{Capabilities: &sdk.ClientCapabilities{}}).Connect(ctx, &sdk.StreamableClientTransport{Endpoint: agent.MCPEndpoint, HTTPClient: &http.Client{Transport: w, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}, DisableStandaloneSSE: true, MaxRetries: -1}, nil)
	if err != nil {
		t.Fatal("SDK negotiation failed")
	}
	t.Cleanup(func() { session.Close() })
	return session, w
}
func call(ctx context.Context, s *sdk.ClientSession) (billing.DraftOutput, error) {
	result, err := s.CallTool(ctx, &sdk.CallToolParams{Name: billing.CreateDraft, Arguments: args})
	if err != nil {
		return billing.DraftOutput{}, err
	}
	if result.IsError {
		return billing.DraftOutput{}, errors.New("tool denied")
	}
	raw, err := json.Marshal(result.StructuredContent)
	if err != nil {
		return billing.DraftOutput{}, err
	}
	normalized := agent.ToolResult{ToolID: billing.CreateDraft, Result: raw}
	envelope, _ := json.Marshal(normalized)
	if agent.DecodeToolResult(envelope, &normalized) != nil {
		return billing.DraftOutput{}, errors.New("invalid business result")
	}
	var draft billing.DraftOutput
	if json.Unmarshal(raw, &draft) != nil {
		return draft, errors.New("invalid output")
	}
	return draft, nil
}
func TestConcurrentDuplicate(t *testing.T) {
	session, _ := connect(t, false)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	values := make([]billing.DraftOutput, 2)
	errs := make([]error, 2)
	var group sync.WaitGroup
	start := make(chan struct{})
	for i := range 2 {
		group.Add(1)
		go func() { defer group.Done(); <-start; values[i], errs[i] = call(ctx, session) }()
	}
	close(start)
	group.Wait()
	for i, e := range errs {
		if e != nil {
			t.Fatalf("concurrent call %d failed", i)
		}
	}
	if values[0].Invoice.ID != values[1].Invoice.ID || values[0].Invoice.Total != 25000 || values[1].Invoice.Total != 25000 {
		t.Fatal("duplicate response invariant")
	}
	t.Logf("same committed invoice %s; independent SQL row/ledger count and reset remain required", values[0].Invoice.ID)
}
func TestTimeoutAfterCommittedResponse(t *testing.T) {
	session, w := connect(t, true)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := call(ctx, session); err == nil {
		t.Fatal("response timeout was not injected")
	}
	w.mu.Lock()
	lost := w.lostID
	w.mu.Unlock()
	if lost == "" {
		t.Fatal("no real committed response discarded")
	}
	draft, err := call(ctx, session)
	if err != nil || draft.Invoice.ID != lost || draft.Invoice.Total != 25000 {
		t.Fatal("same-key retry changed committed invoice")
	}
	t.Logf("retry preserved committed invoice %s; fault was injected after the actual server response", lost)
}
