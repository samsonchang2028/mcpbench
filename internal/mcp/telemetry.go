package mcp

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"time"

	"mcpbench/internal/billing"
	"mcpbench/internal/store"
	"mcpbench/observability"
)

func databaseObserver(w *observability.Writer, phase, parent string) store.Observer {
	return func(operation, tx string) (func(error) error, error) {
		// Frozen Event semantics classify execution SQL reads as read_tool,
		// including same-key duplicate retrieval; verifier SQL is replay only.
		if phase == "verification" {
			if operation == "create_draft" {
				return nil, invalid
			}
			operation = "replay"
		} else if phase == "execution" {
			if operation == "replay" {
				operation = "read_tool"
			}
		} else {
			return nil, invalid
		}
		id := make([]byte, 16)
		if _, err := rand.Read(id); err != nil {
			return nil, invalid
		}
		call := "db-" + hex.EncodeToString(id)
		start := time.Now()
		if err := w.Emit(observability.Record{Type: "db.started", Phase: phase, Status: "ok", CallID: call, ParentCallID: parent, Data: map[string]any{"operation": operation, "transaction_id": tx}}); err != nil {
			return nil, err
		}
		return func(outcome error) error {
			kind, status := "db.completed", "ok"
			data := map[string]any{"operation": operation, "transaction_id": tx, "duration_ms": float64(time.Since(start)) / float64(time.Millisecond)}
			if outcome == nil {
				data["rows_affected"] = nil
			} else {
				kind, status = "db.failed", "error"
				code := "db_error"
				certainty := "observed"
				var b *billing.Error
				if errors.As(outcome, &b) {
					code = failureCode(b.Code)
					if b.OutcomeUnknown {
						certainty = "uncertain"
						code = "settlement_unknown"
					}
				}
				data["failure"] = map[string]any{"stage": phase, "code": code, "call_id": call, "reason": code, "attribution": certainty, "disposition": "terminal"}
			}
			return w.Emit(observability.Record{Type: kind, Phase: phase, Status: status, CallID: call, ParentCallID: parent, Data: data})
		}, nil
	}
}
