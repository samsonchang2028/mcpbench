package ollama

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"time"
)

const Endpoint = "http://127.0.0.1:11434/api/chat"

type Function struct {
	Name        string          `json:"name"`
	Arguments   json.RawMessage `json:"arguments,omitempty"`
	Description string          `json:"description,omitempty"`
	Parameters  any             `json:"parameters,omitempty"`
}
type Tool struct {
	Type     string   `json:"type"`
	Function Function `json:"function"`
}
type ToolCall struct {
	ID       string   `json:"id,omitempty"`
	Function Function `json:"function"`
}
type Message struct {
	Role       string     `json:"role"`
	Content    string     `json:"content"`
	ToolCalls  []ToolCall `json:"tool_calls,omitempty"`
	ToolName   string     `json:"tool_name,omitempty"`
	ToolCallID string     `json:"tool_call_id,omitempty"`
}
type Request struct {
	Model     string         `json:"model"`
	Messages  []Message      `json:"messages"`
	Tools     []Tool         `json:"tools"`
	Stream    bool           `json:"stream"`
	Options   map[string]any `json:"options"`
	Think     *bool          `json:"think,omitempty"`
	KeepAlive *string        `json:"keep_alive,omitempty"`
}
type Response struct {
	Message         Message `json:"message"`
	Done            bool    `json:"done"`
	PromptEvalCount *int    `json:"prompt_eval_count"`
	EvalCount       *int    `json:"eval_count"`
}
type Client struct{ HTTP *http.Client }

func HTTPClient() *http.Client {
	return &http.Client{Transport: &http.Transport{Proxy: nil, ResponseHeaderTimeout: 120 * time.Second}, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("redirect denied") }}
}
func New() *Client { return &Client{HTTP: HTTPClient()} }
func (c *Client) Chat(ctx context.Context, r Request) (Response, error) {
	var out Response
	b, e := json.Marshal(r)
	if e != nil {
		return out, errors.New("model request invalid")
	}
	req, e := http.NewRequestWithContext(ctx, "POST", Endpoint, bytes.NewReader(b))
	if e != nil {
		return out, e
	}
	req.Header.Set("Content-Type", "application/json")
	resp, e := c.HTTP.Do(req)
	if e != nil {
		return out, errors.New("model transport failed")
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return out, errors.New("model response failed")
	}
	b, e = io.ReadAll(io.LimitReader(resp.Body, 1048577))
	if e != nil || len(b) > 1048576 {
		return out, errors.New("model response oversized")
	}
	if _, e = strictJSON(b, true); e != nil {
		return out, errors.New("model JSON invalid")
	}
	if json.Unmarshal(b, &out) != nil || !out.Done || out.Message.Role != "assistant" || out.PromptEvalCount != nil && *out.PromptEvalCount < 0 || out.EvalCount != nil && *out.EvalCount < 0 {
		return out, errors.New("model response invalid")
	}
	return out, nil
}
