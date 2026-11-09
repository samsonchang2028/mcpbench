package agent

import (
	"encoding/json"
	"mcpbench/observability"
	"strings"
	"time"
)

// ValidateEvent validates only the explicitly emitted agent subset. Unsupported
// event kinds fail closed. The writer independently enforces stream correlation.
func ValidateEvent(e map[string]any) error {
	b, _ := json.Marshal(e)
	if Validate("Event", b) != nil {
		return invalid
	}
	if e["source"] != "agent" || !validCalendar(time.RFC3339Nano, e["timestamp"].(string)) {
		return invalid
	}
	d := e["data"].(map[string]any)
	kind := e["event_type"].(string)
	switch kind {
	case "model.started":
	case "model.completed", "model.failed":
		if (d["prompt_tokens"] == nil || d["output_tokens"] == nil) != (d["counts_unavailable_reason"] != nil) {
			return invalid
		}
	case "tool.started":
		b, _ := json.Marshal(d["arguments"])
		if ValidateArguments(d["tool_id"].(string), b) != nil {
			return invalid
		}
	case "tool.completed", "tool.failed":
		if d["tool_result"] != nil {
			b, _ := json.Marshal(d["tool_result"])
			var r ToolResult
			if DecodeToolResult(b, &r) != nil || r.ToolID != d["tool_id"] || r.IsError != (kind == "tool.failed") {
				return invalid
			}
		}
	case "agent.finished":
		r := d["result"].(map[string]any)
		if r["run_id"] != e["run_id"] || r["attempt_id"] != e["attempt_id"] {
			return invalid
		}
	case "failure":
	default:
		return invalid
	}
	if f, ok := d["failure"].(map[string]any); ok {
		if f["disposition"] == "recovered" && !strings.Contains("|unknown_tool|invalid_arguments|unauthorized_attempt|tool_error|db_error|tool_timeout|idempotency_conflict|protocol_error|", "|"+f["code"].(string)+"|") {
			return invalid
		}
	}
	return nil
}
func tree(v any) map[string]any {
	b, _ := json.Marshal(v)
	var m map[string]any
	json.Unmarshal(b, &m)
	return m
}
func failure(code, phase, call, disposition string) Failure {
	var c *string
	if call != "" {
		c = &call
	}
	return Failure{phase, code, c, code, "observed", disposition}
}
func emit(w *observability.Writer, kind, phase, status, call string, data map[string]any) error {
	if w == nil {
		return invalid
	}
	return w.Emit(observability.Record{Type: kind, Phase: phase, Status: status, CallID: call, Data: data})
}
func DecodeToolResult(b []byte, out *ToolResult) error {
	if Decode("ToolResult", b, out) != nil {
		return invalid
	}
	if out.IsError {
		if out.Error.Retryable && out.Error.Code != "db_error" && out.Error.Code != "tool_timeout" {
			return invalid
		}
		return nil
	}
	if out.ToolID != "billing_create_draft_invoice" {
		return nil
	}
	var d struct {
		Invoice struct {
			InvoiceID   string `json:"invoice_id"`
			InvoiceDate string `json:"invoice_date"`
			DueDate     string `json:"due_date"`
			CreatedAt   string `json:"created_at"`
			Subtotal    int64  `json:"subtotal_cents"`
			Total       int64  `json:"total_cents"`
		} `json:"invoice"`
		Lines []struct {
			InvoiceID string `json:"invoice_id"`
			ItemID    string `json:"item_id"`
			Number    int    `json:"line_number"`
			Quantity  int64  `json:"quantity"`
			Price     int64  `json:"unit_price_cents"`
			Total     int64  `json:"line_total_cents"`
		} `json:"lines"`
	}
	if json.Unmarshal(out.Result, &d) != nil {
		return invalid
	}
	if !validCalendar(time.DateOnly, d.Invoice.InvoiceDate) || !validCalendar(time.DateOnly, d.Invoice.DueDate) || d.Invoice.DueDate < d.Invoice.InvoiceDate || !validCalendar(time.RFC3339Nano, d.Invoice.CreatedAt) {
		return invalid
	}
	seen := map[string]bool{}
	nums := map[int]bool{}
	sum := int64(0)
	for _, l := range d.Lines {
		if l.InvoiceID != d.Invoice.InvoiceID || seen[l.ItemID] || nums[l.Number] || l.Number < 1 || l.Number > len(d.Lines) || l.Quantity*l.Price != l.Total {
			return invalid
		}
		seen[l.ItemID] = true
		nums[l.Number] = true
		sum += l.Total
		if sum > 9007199254740991 {
			return invalid
		}
	}
	if sum != d.Invoice.Subtotal || sum != d.Invoice.Total {
		return invalid
	}
	return nil
}

// Schema patterns constrain the spelling; parsing enforces real calendar dates.
func validCalendar(layout, value string) bool {
	t, e := time.Parse(layout, value)
	return e == nil && t.Year() >= 1
}
