// Package mcp implements the frozen three-tool Streamable HTTP transport.
package mcp

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
	"mcpbench/internal/agent"
	"mcpbench/internal/billing"
	"mcpbench/internal/store"
	"mcpbench/observability"
)

const MaxBody = 1 << 20
const ProtocolVersion = "2026-07-28"

type Service interface {
	Authorize(context.Context, billing.Access) ([]string, error)
	Call(context.Context, billing.Access, string, json.RawMessage) (any, error)
}

// Events resolves a trusted run-specific writer and phase. It must neither
// derive routing from model arguments nor create a new writer per call.
type Events func(runID, attemptID string) (*observability.Writer, string, error)
type Options struct {
	Service Service
	Ready   func(context.Context) error
	Events  Events
	// Diagnostic retains only private unknown settlement evidence, never secrets.
	Diagnostic func(runID, attemptID string, outcomeUnknown bool)
}
type identity struct {
	access billing.Access
	acl    []string
}
type identityKey struct{}
type catalogEntry struct {
	Name, Description string
	InputRef          string `json:"input_ref"`
	OutputRef         string `json:"output_ref"`
}

func New(o Options) (http.Handler, error) {
	if o.Service == nil || o.Ready == nil {
		return nil, invalid
	}
	var catalog struct {
		Tools []catalogEntry `json:"tools"`
	}
	if json.Unmarshal(catalogBytes, &catalog) != nil || len(catalog.Tools) < 3 {
		return nil, invalid
	}
	s := sdk.NewServer(&sdk.Implementation{Name: "mcpbench-billing", Version: "1"}, &sdk.ServerOptions{Capabilities: &sdk.ServerCapabilities{Tools: &sdk.ToolCapabilities{}}})
	for _, entry := range catalog.Tools[:3] {
		input, e := resolved(entry.InputRef)
		if e != nil {
			return nil, e
		}
		output, e := resolved(entry.OutputRef)
		if e != nil {
			return nil, e
		}
		name := entry.Name
		s.AddTool(&sdk.Tool{Name: name, Description: entry.Description, InputSchema: input, OutputSchema: output}, func(ctx context.Context, r *sdk.CallToolRequest) (*sdk.CallToolResult, error) {
			who, ok := ctx.Value(identityKey{}).(identity)
			if !ok {
				return toolFailure(billing.Fail("authorization_denied")), nil
			}
			args := r.Params.Arguments
			if agent.ValidateArguments(name, args) != nil {
				return toolFailure(billing.Fail("invalid_arguments")), nil
			}
			var writer *observability.Writer
			phase := ""
			call := ""
			if o.Events != nil {
				var err error
				writer, phase, err = o.Events(who.access.RunID, who.access.AttemptID)
				if err != nil || writer == nil || (phase != "execution" && phase != "verification") {
					return toolFailure(billing.Fail("tool_error")), nil
				}
				id := make([]byte, 16)
				if _, err = rand.Read(id); err != nil {
					return toolFailure(billing.Fail("tool_error")), nil
				}
				call = "mcp-" + hex.EncodeToString(id)
				var arguments any
				json.Unmarshal(args, &arguments)
				if writer.Emit(observability.Record{Type: "tool.started", Phase: phase, Status: "ok", CallID: call, Data: map[string]any{"tool_id": name, "arguments": arguments, "retry_index": 0}}) != nil {
					return toolFailure(billing.Fail("tool_error")), nil
				}
			}
			if writer != nil {
				ctx = store.WithObserver(ctx, databaseObserver(writer, phase, call))
			}
			start := time.Now()
			value, err := o.Service.Call(ctx, who.access, name, args)
			var result *sdk.CallToolResult
			if err != nil {
				var b *billing.Error
				if errors.As(err, &b) && b.OutcomeUnknown && o.Diagnostic != nil {
					o.Diagnostic(who.access.RunID, who.access.AttemptID, true)
				}
				result = toolFailure(err)
			} else {
				raw, e := json.Marshal(value)
				envelope := agent.ToolResult{ToolID: name, Result: raw}
				encoded, _ := json.Marshal(envelope)
				if e != nil || len(raw) > MaxBody-4096 || agent.DecodeToolResult(encoded, &envelope) != nil {
					result = toolFailure(billing.Fail("tool_error"))
				} else {
					result = &sdk.CallToolResult{StructuredContent: value, Content: []sdk.Content{&sdk.TextContent{Text: string(raw)}}}
				}
			}
			encodedResult, encodeError := json.Marshal(result)
			if encodeError != nil || len(encodedResult) > MaxBody-4096 {
				result = toolFailure(billing.Fail("tool_error"))
			}
			if writer != nil {
				envelope := map[string]any{"tool_id": name, "is_error": result.IsError}
				if result.IsError {
					envelope["error"] = jsonTree(result.StructuredContent)
				} else {
					envelope["result"] = jsonTree(result.StructuredContent)
				}
				kind, status := "tool.completed", "ok"
				data := map[string]any{"tool_id": name, "duration_ms": float64(time.Since(start)) / float64(time.Millisecond), "tool_result": envelope}
				if result.IsError {
					kind, status = "tool.failed", "error"
					b := result.StructuredContent.(*billing.Error)
					data["failure"] = map[string]any{"stage": phase, "code": failureCode(b.Code), "call_id": call, "reason": b.Code, "attribution": "observed", "disposition": "terminal"}
				}
				if writer.Emit(observability.Record{Type: kind, Phase: phase, Status: status, CallID: call, Data: data}) != nil {
					return toolFailure(billing.Fail("tool_error")), nil
				}
			}
			return result, nil
		})
	}
	s.AddReceivingMiddleware(func(next sdk.MethodHandler) sdk.MethodHandler {
		return func(ctx context.Context, method string, r sdk.Request) (sdk.Result, error) {
			result, err := next(ctx, method, r)
			if err == nil && method == "tools/list" {
				who, ok := ctx.Value(identityKey{}).(identity)
				if !ok {
					return nil, invalid
				}
				listed := result.(*sdk.ListToolsResult)
				filtered := make([]*sdk.Tool, 0, 3)
				for _, t := range listed.Tools {
					for _, allowed := range who.acl {
						if t.Name == allowed {
							filtered = append(filtered, t)
							break
						}
					}
				}
				listed.Tools = filtered
			}
			return result, err
		}
	})
	transport := sdk.NewStreamableHTTPHandler(func(*http.Request) *sdk.Server { return s }, &sdk.StreamableHTTPOptions{Stateless: true, JSONResponse: true, MaxRequestBodyBytes: MaxBody, PropagateRequestCancellation: true})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !allowedHost(r.Host) || (r.URL.Path != "/healthz" && (r.Host == "127.0.0.1:8080" || r.Host == "localhost:8080")) || !allowedOrigin(r.Header) {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		if r.URL.Path == "/healthz" {
			if r.Method != "GET" {
				http.Error(w, "method", 405)
				return
			}
			ctx, cancel := context.WithTimeout(r.Context(), billing.OperationLimit)
			defer cancel()
			if o.Ready(ctx) != nil {
				http.Error(w, "unavailable", 503)
				return
			}
			w.Header().Set("Content-Type", "text/plain")
			io.WriteString(w, "ready\n")
			return
		}
		if r.URL.Path != "/mcp" || r.URL.RawQuery != "" {
			http.NotFound(w, r)
			return
		}
		a, err := access(r.Header)
		if err != nil {
			http.Error(w, "unauthorized", 401)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), billing.OperationLimit)
		defer cancel()
		acl, err := o.Service.Authorize(ctx, a)
		if err != nil {
			var b *billing.Error
			if errors.As(err, &b) && b.OutcomeUnknown && o.Diagnostic != nil {
				o.Diagnostic(a.RunID, a.AttemptID, true)
			}
			http.Error(w, "unauthorized", 401)
			return
		}
		ctx = context.WithValue(ctx, identityKey{}, identity{a, acl})
		r = r.WithContext(ctx)
		if r.Method == "POST" {
			b, e := io.ReadAll(io.LimitReader(r.Body, MaxBody+1))
			r.Body.Close()
			if e != nil || len(b) > MaxBody {
				http.Error(w, "body limit", 413)
				return
			}
			// Let the actual SDK produce the malformed JSON-RPC error, including for
			// strict lexical violations its general JSON decoder would otherwise admit.
			if _, e = agent.StrictJSON(b); e != nil {
				b = []byte("{")
			}
			r.Body = io.NopCloser(bytes.NewReader(b))
			r.ContentLength = int64(len(b))
		}
		bounded := &responseBuffer{header: make(http.Header)}
		transport.ServeHTTP(bounded, r)
		if bounded.overflow {
			http.Error(w, "response limit", 500)
			return
		}
		for k, v := range bounded.header {
			w.Header()[k] = v
		}
		status := bounded.status
		if status == 0 {
			status = 200
		}
		w.WriteHeader(status)
		w.Write(bounded.body.Bytes())
	}), nil
}

func toolFailure(err error) *sdk.CallToolResult {
	safe := billing.Fail("tool_error")
	var b *billing.Error
	if errors.As(err, &b) {
		raw, _ := json.Marshal(b)
		if validate("ToolError", raw) == nil && (!b.Retryable || b.Code == "db_error" || b.Code == "tool_timeout") {
			// Messages are categories, even when a faulty adapter returns raw diagnostics.
			safe = &billing.Error{Code: b.Code, Message: b.Code, Retryable: b.Retryable}
		}
	}
	raw, _ := json.Marshal(safe)
	return &sdk.CallToolResult{IsError: true, StructuredContent: safe, Content: []sdk.Content{&sdk.TextContent{Text: string(raw)}}}
}

var capability = regexp.MustCompile(`^[0-9a-f]{64}$`)

func access(h http.Header) (billing.Access, error) {
	keys := []string{"Authorization", "X-MCPBench-Run-ID", "X-MCPBench-Attempt-ID", "X-MCPBench-Idempotency-Key"}
	for _, k := range keys {
		if len(h.Values(k)) != 1 {
			return billing.Access{}, invalid
		}
	}
	token, ok := strings.CutPrefix(h.Get("Authorization"), "Bearer ")
	a := billing.Access{RunID: h.Get(keys[1]), AttemptID: h.Get(keys[2]), IdempotencyKey: h.Get(keys[3]), Capability: token}
	if !ok || !capability.MatchString(token) || !billing.Identifier.MatchString(a.RunID) || !billing.Identifier.MatchString(a.AttemptID) || !billing.Identifier.MatchString(a.IdempotencyKey) {
		return billing.Access{}, invalid
	}
	return a, nil
}
func allowedHost(h string) bool {
	return h == "127.0.0.1:18081" || h == "localhost:18081" || h == "127.0.0.1:8080" || h == "localhost:8080"
}
func allowedOrigin(h http.Header) bool {
	v := h.Values("Origin")
	return len(v) == 0 || (len(v) == 1 && (v[0] == "" || v[0] == "http://127.0.0.1:18081" || v[0] == "http://localhost:18081"))
}

type responseBuffer struct {
	header   http.Header
	body     bytes.Buffer
	status   int
	overflow bool
}

func (b *responseBuffer) Header() http.Header { return b.header }
func (b *responseBuffer) WriteHeader(s int) {
	if b.status == 0 {
		b.status = s
	}
}
func (b *responseBuffer) Write(p []byte) (int, error) {
	if b.body.Len()+len(p) > MaxBody {
		b.overflow = true
		return 0, invalid
	}
	return b.body.Write(p)
}

func failureCode(code string) string {
	switch code {
	case "invalid_arguments", "authorization_denied", "db_error", "tool_timeout", "idempotency_conflict":
		return code
	default:
		return "tool_error"
	}
}

func jsonTree(v any) any { b, _ := json.Marshal(v); var out any; json.Unmarshal(b, &out); return out }
