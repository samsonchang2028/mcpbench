package store

import (
	"context"
	"errors"
	"mcpbench/internal/billing"
	"testing"
)

func TestTelemetryFollowsActualTransactionAcknowledgment(t *testing.T) {
	for _, mode := range []string{"commit", "commit-unknown", "rollback", "rollback-unknown"} {
		t.Run(mode, func(t *testing.T) {
			db, a := fixture()
			if mode == "commit-unknown" {
				db.tx.commitErr = errors.New("lost ACK")
			}
			if mode == "rollback-unknown" {
				db.tx.rollbackErr = errors.New("lost ACK")
			}
			started, closed := false, false
			observer := Observer(func(op, tx string) (func(error) error, error) {
				if op != "read_tool" || !billing.Identifier.MatchString(tx) || db.tx.commits+db.tx.rollbacks != 0 {
					t.Fatal("start not at SQL boundary")
				}
				started = true
				return func(err error) error {
					if db.tx.commits+db.tx.rollbacks != 1 {
						t.Fatal("terminal before actual transaction outcome")
					}
					closed = true
					if mode == "commit" && err != nil {
						t.Fatal(err)
					}
					if mode != "commit" && err == nil {
						t.Fatal("fabricated success")
					}
					if mode == "commit-unknown" || mode == "rollback-unknown" {
						var b *billing.Error
						if !errors.As(err, &b) || !b.OutcomeUnknown {
							t.Fatal("unknown ACK lost")
						}
					}
					return nil
				}, nil
			})
			err := New(db).WithSession(WithObserver(context.Background(), observer), a, billing.ListCustomers, func(s billing.Session) error {
				if err := s.(*session).events.start("read_tool"); err != nil {
					return err
				}
				if mode == "rollback" || mode == "rollback-unknown" {
					return billing.Fail("invalid_arguments")
				}
				return nil
			})
			if !started || !closed || (mode == "commit" && err != nil) || (mode != "commit" && err == nil) {
				t.Fatal("missing truthful telemetry", err)
			}
		})
	}
}
func TestTelemetryStartFailurePreventsApplicationSQL(t *testing.T) {
	db, a := fixture()
	ctx := WithObserver(context.Background(), func(string, string) (func(error) error, error) { return nil, errors.New("artifact failed") })
	_, err := (billing.Service{Repo: New(db)}).Call(ctx, a, billing.ListCustomers, []byte(`{}`))
	var b *billing.Error
	if !errors.As(err, &b) || b.Code != "tool_error" || db.tx.commits != 0 || db.tx.rollbacks != 1 {
		t.Fatal("unlogged application operation admitted", err)
	}
}
