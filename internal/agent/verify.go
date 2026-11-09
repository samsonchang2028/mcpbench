package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"math"
	"mcpbench/observability"
	"reflect"
	"time"
)

func canonical(v any) []byte {
	var b bytes.Buffer
	e := json.NewEncoder(&b)
	e.SetEscapeHTML(false)
	e.Encode(v)
	return bytes.TrimSuffix(b.Bytes(), []byte("\n"))
}
func ValidateVerification(q VerificationRequest, a AuthInput) error {
	b, _ := json.Marshal(q)
	if Validate("VerificationRequest", b) != nil || validateAuth(a, q.RunID, q.AttemptID, "verify") != nil || q.IdempotencyKey != a.IdempotencyKey || ValidateArguments(CreateTool, q.OriginalArguments) != nil || ValidateArguments(CreateTool, q.ConflictArguments) != nil {
		return invalid
	}
	var original, changed map[string]any
	json.Unmarshal(q.OriginalArguments, &original)
	json.Unmarshal(q.ConflictArguments, &changed)
	if hash(canonical(map[string]any{"tool_id": CreateTool, "arguments": original})) != q.OriginalRequestHash {
		return invalid
	}
	lines := original["lines"].([]any)
	line := lines[0].(map[string]any)
	quantity := line["quantity"].(float64)
	if quantity == 1000 {
		line["quantity"] = quantity - 1
	} else {
		line["quantity"] = quantity + 1
	}
	if !reflect.DeepEqual(original, changed) {
		return invalid
	}
	start, e := time.Parse(time.RFC3339Nano, q.Budget.StartedAt)
	if e != nil {
		return invalid
	}
	end, e := time.Parse(time.RFC3339Nano, q.Budget.DeadlineAt)
	if e != nil || end.Sub(start) != 30*time.Second || q.Budget.RemainingMS != math.Max(0, 30000-q.Budget.ElapsedMS) || q.Budget.OperationTimeoutMS != math.Min(5000, q.Budget.RemainingMS) {
		return invalid
	}
	return nil
}

// Verify performs precisely two constrained calls and never invokes a model,
// lists tools, retries, creates a capability, or claims database settlement.
func Verify(ctx context.Context, q VerificationRequest, a AuthInput, t Tools, w *observability.Writer) (out VerifierResult, err error) {
	return VerifySince(ctx, q, a, t, w, time.Now())
}

// VerifySince retains the invocation entry time, including MCP startup, instead
// of granting the supplied remaining budget again after negotiation.
func VerifySince(ctx context.Context, q VerificationRequest, a AuthInput, t Tools, w *observability.Writer, entered time.Time) (out VerifierResult, err error) {
	out = VerifierResult{SchemaVersion: 1, RunID: q.RunID, AttemptID: q.AttemptID, TaskID: q.TaskID, TaskHash: q.TaskHash, ConfigHash: q.ConfigHash, Status: "failed", InvoiceID: q.InvoiceID, IdempotencyKey: q.IdempotencyKey, OriginalRequestHash: q.OriginalRequestHash, Budget: q.Budget, Checks: []VerifierCheck{}}
	if ValidateVerification(q, a) != nil || t == nil || w == nil {
		return out, invalid
	}
	deadline, _ := time.Parse(time.RFC3339Nano, q.Budget.DeadlineAt)
	remaining := func() time.Duration {
		local := time.Duration(q.Budget.RemainingMS*float64(time.Millisecond)) - time.Since(entered)
		wall := time.Until(deadline)
		if wall < local {
			return wall
		}
		return local
	}
	defer func() {
		elapsed := q.Budget.ElapsedMS + float64(time.Since(entered).Microseconds())/1000
		wall := 30000 - float64(time.Until(deadline).Microseconds())/1000
		if wall > elapsed {
			elapsed = wall
		}
		elapsed = math.Ceil(elapsed)
		out.Budget.ElapsedMS = elapsed
		out.Budget.RemainingMS = math.Max(0, 30000-elapsed)
		out.Budget.OperationTimeoutMS = math.Min(5000, out.Budget.RemainingMS)
	}()
	for i, args := range []json.RawMessage{q.OriginalArguments, q.ConflictArguments} {
		left := remaining()
		if left <= 0 || ctx.Err() != nil {
			out.Status = "timeout"
			if e := emit(w, "failure", "verification", "error", "", map[string]any{"failure": tree(failure("verification_failed", "verification", "", "terminal"))}); e != nil {
				return out, e
			}
			return out, nil
		}
		if left > 5*time.Second {
			left = 5 * time.Second
		}
		call := []string{"verify-replay", "verify-conflict"}[i]
		start := time.Now()
		argtree, _ := StrictJSON(args)
		if e := emit(w, "tool.started", "verification", "ok", call, map[string]any{"tool_id": CreateTool, "arguments": argtree, "retry_index": 0}); e != nil {
			return out, e
		}
		op, cancel := context.WithTimeout(ctx, left)
		r, e := t.Call(op, CreateTool, args)
		oe := op.Err()
		cancel()
		out.Calls++
		check := VerifierCheck{Check: q.Checks[i]}
		duration := float64(time.Since(start).Microseconds()) / 1000
		raw, _ := json.Marshal(r)
		valid := e == nil && oe == nil && DecodeToolResult(raw, &r) == nil && r.ToolID == CreateTool
		if valid {
			check.ToolResult = &r
			if i == 0 {
				check.Pass = !r.IsError && replayMatches(r, q)
			} else {
				check.Pass = r.IsError && r.Error.Code == "idempotency_conflict"
			}
		}
		if !valid {
			f := failure("verification_failed", "verification", call, "terminal")
			check.Failure = &f
		}
		kind, status := "tool.completed", "ok"
		data := map[string]any{"tool_id": CreateTool, "duration_ms": duration, "tool_result": nil}
		if valid {
			data["tool_result"] = tree(r)
		}
		if !valid || r.IsError {
			kind = "tool.failed"
			status = "error"
			f := failure("verification_failed", "verification", call, "terminal")
			if check.Pass {
				f = failure("idempotency_conflict", "verification", call, "recovered")
			}
			data["failure"] = tree(f)
		}
		if e := emit(w, kind, "verification", status, call, data); e != nil {
			return out, e
		}
		if valid && !r.IsError && !check.Pass {
			if e := emit(w, "failure", "verification", "error", call, map[string]any{"failure": tree(failure("verification_failed", "verification", call, "terminal"))}); e != nil {
				return out, e
			}
		}
		out.Checks = append(out.Checks, check)
		if !check.Pass {
			return out, nil
		}
	}
	if remaining() <= 0 {
		out.Status = "timeout"
	} else {
		out.Status = "completed"
	}
	return out, nil
}
func replayMatches(r ToolResult, q VerificationRequest) bool {
	var d map[string]any
	json.Unmarshal(r.Result, &d)
	invoice, ok := d["invoice"].(map[string]any)
	if !ok || invoice["invoice_id"] != q.InvoiceID {
		return false
	}
	args := map[string]any{}
	for _, k := range []string{"customer_id", "invoice_date", "due_date"} {
		args[k] = invoice[k]
	}
	lines := []any{}
	for _, v := range d["lines"].([]any) {
		l := v.(map[string]any)
		lines = append(lines, map[string]any{"item_id": l["item_id"], "quantity": l["quantity"]})
	}
	args["lines"] = lines
	var original any
	json.Unmarshal(q.OriginalArguments, &original)
	return reflect.DeepEqual(args, original)
}
