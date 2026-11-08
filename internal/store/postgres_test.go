package store

// These request-level PostgreSQL cases are deliberately opt-in and UNRUN in
// T012. T018 owns admission, provisioning, secret files and lifecycle fences.
import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"mcpbench/internal/billing"
)

// A private mode-0600 file from the trusted integration controller supplies only
// Access fields. The test never creates a run, mints tokens or resets schemas.
// The harness must provision an unused executing run with the canonical fixture,
// the three-tool drafter ACL and expiry covering this test. Use a distinct run
// for each case; retained state is evidence for its independent DB oracle.
func liveAccess(t *testing.T, env string) billing.Access {
	t.Helper()
	if os.Getenv("MCPBENCH_LIVE_DB") != "dedicated-container" {
		t.Skip("UNRUN: requires T018 owned database admission")
	}
	p := os.Getenv(env)
	if p == "" {
		t.Skip("UNRUN: no trusted prepared run for " + env)
	}
	fi, e := os.Lstat(p)
	if e != nil {
		t.Fatal("private access input unavailable")
	}
	if !fi.Mode().IsRegular() || fi.Mode().Perm() != 0600 {
		t.Fatal("access input must be a regular mode-0600 private file")
	}
	raw, e := os.ReadFile(p)
	if e != nil {
		t.Fatal("access input unreadable")
	}
	var a billing.Access
	if json.Unmarshal(raw, &a) != nil || !billing.Identifier.MatchString(a.RunID) || !billing.Identifier.MatchString(a.AttemptID) || !billing.Identifier.MatchString(a.IdempotencyKey) || !hexDigest.MatchString(a.Capability) {
		t.Fatal("invalid private access input")
	}
	return a
}
func liveConn(t *testing.T) *pgx.Conn {
	t.Helper()
	if os.Getenv("PGPASSFILE") == "" {
		t.Fatal("private project passfile required")
	}
	cfg, e := pgx.ParseConfig("host=db port=5432 dbname=mcpbench user=mcpbench_service sslmode=disable connect_timeout=2")
	if e != nil {
		t.Fatal("invalid fixed connection configuration")
	}
	cfg.Host = "db"
	cfg.Port = 5432
	cfg.Database = "mcpbench"
	cfg.User = "mcpbench_service"
	cfg.Fallbacks = nil
	cfg.RuntimeParams = map[string]string{"application_name": "mcpbench-t012-integration"}
	ctx, cancel := context.WithTimeout(context.Background(), billing.OperationLimit)
	defer cancel()
	conn, e := pgx.ConnectConfig(ctx, cfg)
	if e != nil {
		t.Fatal("owned project service connection unavailable")
	}
	t.Cleanup(func() {
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		_ = conn.Close(ctx)
	})
	return conn
}
func liveArgs(q int64) json.RawMessage {
	b, _ := json.Marshal(billing.CreateDraftArgs{CustomerID: "CUST-001", InvoiceDate: "2026-11-07", DueDate: "2026-12-07", Lines: []billing.CreateLine{{ItemID: "SVC-CONSULT", Quantity: q}}})
	return b
}
func TestPostgresConcurrentReplayConflict(t *testing.T) {
	a := liveAccess(t, "MCPBENCH_T012_EXECUTION_ACCESS")
	first, second := liveConn(t), liveConn(t)
	services := []billing.Service{{Repo: New(first)}, {Repo: New(second)}}
	var wg sync.WaitGroup
	results := make([]any, 2)
	errs := make([]error, 2)
	start := make(chan struct{})
	for i := range services {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			results[i], errs[i] = services[i].Call(context.Background(), a, billing.CreateDraft, liveArgs(2))
		}(i)
	}
	close(start)
	wg.Wait()
	for _, e := range errs {
		if e != nil {
			t.Fatalf("concurrent request failed: %v", e)
		}
	}
	one, two := results[0].(billing.DraftOutput), results[1].(billing.DraftOutput)
	if one.Invoice.ID != two.Invoice.ID || one.Invoice.Total != 25000 {
		t.Fatal("replay or total mismatch")
	}
	_, e := services[0].Call(context.Background(), a, billing.CreateDraft, liveArgs(3))
	var be *billing.Error
	if !errors.As(e, &be) || be.Code != "idempotency_conflict" {
		t.Fatalf("conflict %v", e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), billing.OperationLimit)
	defer cancel()
	schema := SchemaName(a.RunID)
	for _, table := range []string{"invoices", "idempotency_records", "invoice_lines"} {
		var n int
		e = first.QueryRow(ctx, "SELECT count(*) FROM "+pgx.Identifier{schema, table}.Sanitize()).Scan(&n)
		if e != nil || n != 1 {
			t.Fatalf("atomic row count for %s: %d, %v", table, n, e)
		}
	}
}
func TestPostgresValidationLeavesNoWrites(t *testing.T) {
	a := liveAccess(t, "MCPBENCH_T012_INVALID_ACCESS")
	conn := liveConn(t)
	svc := billing.Service{Repo: New(conn)}
	bad := billing.CreateDraftArgs{CustomerID: "CUST-001", InvoiceDate: "2026-11-07", DueDate: "2026-12-07", Lines: []billing.CreateLine{{ItemID: "SVC-CONSULT", Quantity: 2}, {ItemID: "MISSING", Quantity: 1}}}
	raw, _ := json.Marshal(bad)
	_, e := svc.Call(context.Background(), a, billing.CreateDraft, raw)
	var be *billing.Error
	if !errors.As(e, &be) || be.Code != "not_found" {
		t.Fatalf("validation outcome %v", e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), billing.OperationLimit)
	defer cancel()
	for _, table := range []string{"invoices", "invoice_lines", "idempotency_records"} {
		var n int
		e = conn.QueryRow(ctx, "SELECT count(*) FROM "+pgx.Identifier{SchemaName(a.RunID), table}.Sanitize()).Scan(&n)
		if e != nil || n != 0 {
			t.Fatalf("partial writes in %s: %d, %v", table, n, e)
		}
	}
}
func TestPostgresVerifierCannotRepairMissingDraft(t *testing.T) {
	a := liveAccess(t, "MCPBENCH_T012_MISSING_VERIFIER_ACCESS")
	svc := billing.Service{Repo: New(liveConn(t))}
	_, e := svc.Call(context.Background(), a, billing.CreateDraft, liveArgs(2))
	var be *billing.Error
	if !errors.As(e, &be) || be.Code != "verification_not_replayable" {
		t.Fatalf("missing verifier ledger: %v", e)
	}
}
