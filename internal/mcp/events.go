package mcp

import (
	"encoding/json"
	"mcpbench/internal/agent"
	"time"
)

// ValidateEvent validates the complete emitted MCP tool-event subset, including
// nested argument/result semantics. Writer separately validates stream closure.
func ValidateEvent(e map[string]any) error {
	raw, err := json.Marshal(e)
	if err != nil || validate("Event", raw) != nil {
		return invalid
	}
	if e["source"] != "mcp" {
		return invalid
	}
	ts, ok := e["timestamp"].(string)
	if !ok {
		return invalid
	}
	t, err := time.Parse(time.RFC3339Nano, ts)
	if err != nil || t.Year() < 1 {
		return invalid
	}
	d := e["data"].(map[string]any)
	name, _ := d["tool_id"].(string)
	switch e["event_type"] {
	case "tool.started":
		b, _ := json.Marshal(d["arguments"])
		return agent.ValidateArguments(name, b)
	case "tool.completed", "tool.failed":
		if d["tool_result"] == nil {
			return invalid
		}
		b, _ := json.Marshal(d["tool_result"])
		var result agent.ToolResult
		if agent.DecodeToolResult(b, &result) != nil || result.ToolID != name || result.IsError != (e["event_type"] == "tool.failed") {
			return invalid
		}
		if f, ok := d["failure"].(map[string]any); ok {
			if f["call_id"] != e["call_id"] || f["stage"] != e["phase"] || f["code"] != failureCode(result.Error.Code) || f["disposition"] != "terminal" {
				return invalid
			}
		}
		if id, ok := d["invoice_id"]; ok {
			var r struct {
				Invoice struct {
					ID string `json:"invoice_id"`
				} `json:"invoice"`
			}
			if json.Unmarshal(result.Result, &r) != nil || id != r.Invoice.ID {
				return invalid
			}
		}
		return nil
	default:
		return invalid
	}
}
