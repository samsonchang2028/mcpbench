package store

import (
	"context"
	"crypto/rand"
	"encoding/hex"
)

// Observer receives actual application SQL boundaries. Started must durably
// publish before SQL. Terminal receives the actual transaction ACK outcome;
// neither a deadline nor a successful callback is positive commit evidence.
// The returned closer is called once, after the encompassing transaction ends.
type Observer func(operation, transactionID string) (func(error) error, error)
type observerKey struct{}

func WithObserver(ctx context.Context, o Observer) context.Context {
	return context.WithValue(ctx, observerKey{}, o)
}

type transactionEvents struct {
	observer Observer
	id       string
	close    []func(error) error
}

func transactionTelemetry(ctx context.Context) *transactionEvents {
	o, _ := ctx.Value(observerKey{}).(Observer)
	return &transactionEvents{observer: o}
}
func (t *transactionEvents) start(op string) error {
	if t == nil || t.observer == nil {
		return nil
	}
	if t.id == "" {
		b := make([]byte, 16)
		if _, e := rand.Read(b); e != nil {
			return e
		}
		t.id = "tx-" + hex.EncodeToString(b)
	}
	close, e := t.observer(op, t.id)
	if e != nil {
		return e
	}
	if close == nil {
		return context.Canceled
	}
	t.close = append(t.close, close)
	return nil
}
func (t *transactionEvents) finish(outcome error) error {
	var first error
	for _, close := range t.close {
		if e := close(outcome); e != nil && first == nil {
			first = e
		}
	}
	t.close = nil
	return first
}
