package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"io"
	"mcpbench/internal/ollama"
	"mime"
	"net"
	"net/http"
)

const MCPEndpoint = "http://127.0.0.1:18081/mcp"

type Tool struct {
	Name        string
	Description string
	InputSchema any
}
type Tools interface {
	List(context.Context) ([]Tool, error)
	Call(context.Context, string, json.RawMessage) (ToolResult, error)
}
type MCPClient struct{ session *mcp.ClientSession }
type authTransport struct {
	base http.RoundTripper
	auth AuthInput
}

func (t authTransport) RoundTrip(r *http.Request) (*http.Response, error) {
	if r.URL.Scheme != "http" || r.URL.Host != "127.0.0.1:18081" || r.URL.Path != "/mcp" {
		return nil, invalid
	}
	r = r.Clone(r.Context())
	r.Header = r.Header.Clone()
	r.Header.Set("Authorization", "Bearer "+t.auth.Capability)
	r.Header.Set("X-MCPBench-Run-ID", t.auth.RunID)
	r.Header.Set("X-MCPBench-Attempt-ID", t.auth.AttemptID)
	r.Header.Set("X-MCPBench-Idempotency-Key", t.auth.IdempotencyKey)
	resp, e := t.base.RoundTrip(r)
	if e != nil {
		var n net.Error
		if errors.As(e, &n) {
			return nil, TransientError{}
		}
		return nil, e
	}
	if resp.StatusCode == 204 || r.Method == "DELETE" {
		return resp, nil
	}
	defer resp.Body.Close()
	content, _, _ := mime.ParseMediaType(resp.Header.Get("Content-Type"))
	if content != "application/json" {
		return nil, invalid
	}
	body, e := io.ReadAll(io.LimitReader(resp.Body, 1048577))
	if e != nil || len(body) > 1048576 {
		return nil, invalid
	}
	if _, e = StrictJSON(body); e != nil {
		return nil, invalid
	}
	resp.Body = io.NopCloser(bytes.NewReader(body))
	return resp, nil
}
func ConnectMCP(ctx context.Context, a AuthInput) (*MCPClient, error) {
	return connectMCP(ctx, a, ollama.HTTPClient().Transport)
}
func connectMCP(ctx context.Context, a AuthInput, base http.RoundTripper) (*MCPClient, error) {
	h := ollama.HTTPClient()
	h.Transport = authTransport{base, a}
	s, e := mcp.NewClient(&mcp.Implementation{Name: "mcpbench-agent", Version: "1"}, &mcp.ClientOptions{Capabilities: &mcp.ClientCapabilities{}}).Connect(ctx, &mcp.StreamableClientTransport{Endpoint: MCPEndpoint, HTTPClient: h, MaxRetries: -1, DisableStandaloneSSE: true}, nil)
	if e != nil {
		return nil, errors.New("MCP connection failed")
	}
	return &MCPClient{s}, nil
}
func (c *MCPClient) Close() error { return c.session.Close() }
func (c *MCPClient) List(ctx context.Context) ([]Tool, error) {
	r, e := c.session.ListTools(ctx, &mcp.ListToolsParams{})
	if e != nil || r.NextCursor != "" {
		return nil, errors.New("MCP catalog incomplete")
	}
	out := []Tool{}
	for _, t := range r.Tools {
		out = append(out, Tool{t.Name, t.Description, t.InputSchema})
	}
	return out, nil
}
func (c *MCPClient) Call(ctx context.Context, name string, args json.RawMessage) (ToolResult, error) {
	r, e := c.session.CallTool(ctx, &mcp.CallToolParams{Name: name, Arguments: args})
	if e != nil {
		var transient TransientError
		if errors.As(e, &transient) {
			return ToolResult{}, transient
		}
		return ToolResult{}, errors.New("MCP call failed")
	}
	var b []byte
	if r.StructuredContent != nil {
		b, e = json.Marshal(r.StructuredContent)
	} else if len(r.Content) == 1 {
		if t, ok := r.Content[0].(*mcp.TextContent); ok {
			b = []byte(t.Text)
		}
	}
	return normalizeMCPResult(name, r.IsError, b, e)
}

// The MCP output schema describes business data; trusted request identity and
// the SDK error bit supply the frozen internal envelope.
func normalizeMCPResult(name string, isError bool, b []byte, transportError error) (ToolResult, error) {
	out := ToolResult{ToolID: name, IsError: isError}
	if transportError != nil {
		return out, invalid
	}
	if isError {
		var toolError ToolError
		if Decode("ToolError", b, &toolError) != nil {
			return out, invalid
		}
		out.Error = &toolError
	} else {
		out.Result = json.RawMessage(b)
	}
	raw, e := json.Marshal(out)
	if e != nil || DecodeToolResult(raw, &out) != nil {
		return out, invalid
	}
	return out, nil
}
