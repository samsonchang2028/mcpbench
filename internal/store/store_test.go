package store

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"mcpbench/internal/billing"
)

func valid() (mapping, billing.Access) {
	a := billing.Access{RunID: "run-store-unit", AttemptID: "attempt-unit", IdempotencyKey: "key-unit", Capability: strings.Repeat("a", 64)}
	sum := sha256.Sum256([]byte(a.Capability))
	digest := hex.EncodeToString(sum[:])
	return mapping{run: a.RunID, attempt: a.AttemptID, tenant: "TENANT-001", principal: "billing-drafter", schema: SchemaName(a.RunID), phase: "executing", workflow: "draft_invoice", tools: []string{billing.ListCustomers, billing.ListItems, billing.CreateDraft}, expiry: time.Now().Add(time.Minute), agent: &digest}, a
}
func TestLockedMappingAuthorization(t *testing.T) {
	m, a := valid()
	if _, e := authorize(m, a, billing.CreateDraft, time.Now()); e != nil {
		t.Fatal(e)
	}
	for _, tc := range []struct {
		name   string
		change func(*mapping, *billing.Access)
	}{
		{"wrong run", func(m *mapping, a *billing.Access) { a.RunID = "run-other" }},
		{"wrong attempt", func(m *mapping, a *billing.Access) { a.AttemptID = "attempt-other" }},
		{"wrong token", func(m *mapping, a *billing.Access) { a.Capability = strings.Repeat("b", 64) }},
		{"expired", func(m *mapping, a *billing.Access) { m.expiry = time.Now().Add(-time.Second) }},
		{"prepared", func(m *mapping, a *billing.Access) { m.phase = "prepared" }},
		{"sealed", func(m *mapping, a *billing.Access) { m.phase = "agent_sealed" }},
		{"wrong generation", func(m *mapping, a *billing.Access) { m.generation = 1 }},
		{"unregistered schema", func(m *mapping, a *billing.Access) { m.schema = "r_" + strings.Repeat("0", 32) }},
		{"injected schema", func(m *mapping, a *billing.Access) { m.schema = `public; SELECT 1` }},
		{"reader create", func(m *mapping, a *billing.Access) { m.principal = "billing-reader" }},
		{"readonly create", func(m *mapping, a *billing.Access) { m.workflow = "read_only" }},
		{"tool excluded", func(m *mapping, a *billing.Access) { m.tools = []string{billing.ListCustomers} }},
		{"unknown tool", func(m *mapping, a *billing.Access) { m.tools = append(m.tools, "shell") }},
		{"missing token", func(m *mapping, a *billing.Access) { m.agent = nil }},
		{"stray scope", func(m *mapping, a *billing.Access) { m.scope = []byte(`{}`) }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			m, a := valid()
			tc.change(&m, &a)
			if _, e := authorize(m, a, billing.CreateDraft, time.Now()); e == nil {
				t.Fatal("authorization admitted")
			}
		})
	}
	m, a = valid()
	m.principal = "billing-reader"
	m.workflow = "read_only"
	m.tools = []string{billing.ListCustomers}
	if _, e := authorize(m, a, billing.ListCustomers, time.Now()); e != nil {
		t.Fatal(e)
	}
}
func TestVerifierMappingScope(t *testing.T) {
	m, a := valid()
	m.phase = "verifying"
	m.generation = 1
	m.verifier = m.agent
	m.agent = nil
	scope := billing.Scope{InvoiceID: "INV-UNIT", IdempotencyKey: a.IdempotencyKey, OriginalRequestHash: strings.Repeat("0", 64)}
	m.scope, _ = json.Marshal(scope)
	if _, e := authorize(m, a, billing.CreateDraft, time.Now()); e != nil {
		t.Fatal(e)
	}
	if _, e := authorize(m, a, billing.ListCustomers, time.Now()); e == nil {
		t.Fatal("verifier could read unrelated customers")
	}
	a.IdempotencyKey = "key-other"
	if _, e := authorize(m, a, billing.CreateDraft, time.Now()); e == nil {
		t.Fatal("verifier key escape")
	}
	a.IdempotencyKey = scope.IdempotencyKey
	m.scope = []byte(`{"invoice_id":"INV-UNIT","idempotency_key":"key-unit","Original_request_hash":"` + strings.Repeat("0", 64) + `"}`)
	if _, e := authorize(m, a, billing.CreateDraft, time.Now()); e == nil {
		t.Fatal("noncanonical scope key accepted")
	}
}

type fakeRow struct{ f func(...any) error }

func (r fakeRow) Scan(v ...any) error { return r.f(v...) }

type fakeTx struct {
	pgx.Tx
	m                      mapping
	queries                []string
	args                   [][]any
	role, login, db        string
	commitErr, rollbackErr error
	commits, rollbacks     int
	queryErr               error
}

func (f *fakeTx) Exec(ctx context.Context, q string, args ...any) (pgconn.CommandTag, error) {
	f.queries = append(f.queries, q)
	f.args = append(f.args, args)
	if _, ok := ctx.Deadline(); !ok {
		panic("session method lost operation bound")
	}
	return pgconn.NewCommandTag("SET"), nil
}
func (f *fakeTx) QueryRow(ctx context.Context, q string, args ...any) pgx.Row {
	f.queries = append(f.queries, q)
	return fakeRow{func(v ...any) error {
		if f.queryErr != nil {
			return f.queryErr
		}
		if strings.Contains(q, "current_user") {
			*v[0].(*string) = f.role
			*v[1].(*string) = f.login
			*v[2].(*string) = f.db
			return nil
		}
		m := f.m
		*v[0].(*string) = m.run
		*v[1].(*string) = m.attempt
		*v[2].(*string) = m.tenant
		*v[3].(*string) = m.principal
		*v[4].(*[]string) = m.tools
		*v[5].(*string) = m.schema
		*v[6].(*string) = m.phase
		*v[7].(*int) = m.generation
		*v[8].(*time.Time) = m.expiry
		*v[9].(**string) = m.agent
		*v[10].(**string) = m.verifier
		*v[11].(*[]byte) = m.scope
		*v[12].(*string) = m.workflow
		return nil
	}}
}
func (f *fakeTx) Commit(context.Context) error   { f.commits++; return f.commitErr }
func (f *fakeTx) Rollback(context.Context) error { f.rollbacks++; return f.rollbackErr }

type fakeDB struct {
	tx       *fakeTx
	options  pgx.TxOptions
	deadline time.Time
	begins   int
}

func (f *fakeDB) BeginTx(ctx context.Context, o pgx.TxOptions) (pgx.Tx, error) {
	f.begins++
	f.options = o
	f.deadline, _ = ctx.Deadline()
	return f.tx, nil
}
func fixture() (*fakeDB, billing.Access) {
	m, a := valid()
	return &fakeDB{tx: &fakeTx{m: m, role: "mcpbench_service", login: "mcpbench_service", db: "mcpbench"}}, a
}
func TestTransactionOrderAndPositiveAck(t *testing.T) {
	db, a := fixture()
	ran := false
	e := New(db).WithSession(context.Background(), a, billing.ListItems, func(s billing.Session) error {
		ran = true
		if !strings.Contains(db.tx.queries[len(db.tx.queries)-1], "FOR SHARE") {
			t.Fatal("callback before registry lock")
		}
		return nil
	})
	if e != nil || !ran || db.tx.commits != 1 || db.tx.rollbacks != 0 {
		t.Fatalf("transaction %v %+v", e, db.tx)
	}
	if db.options.IsoLevel != pgx.ReadCommitted || time.Until(db.deadline) > billing.OperationLimit {
		t.Fatal("missing bounds/read committed")
	}
	if len(db.tx.queries) != 4 {
		t.Fatalf("unexpected SQL %v", db.tx.queries)
	}
	db, a = fixture()
	db.tx.commitErr = errors.New("lost commit ACK")
	e = New(db).WithSession(context.Background(), a, "", func(billing.Session) error { return nil })
	var be *billing.Error
	if !errors.As(e, &be) || !be.OutcomeUnknown || be.Retryable {
		t.Fatalf("commit loss %v", e)
	}
}
func TestAuthorizationDeniesBeforeApplicationSQL(t *testing.T) {
	for _, what := range []string{"expired", "controller", "controller-session", "wrong-db", "sealed", "no-row"} {
		t.Run(what, func(t *testing.T) {
			db, a := fixture()
			switch what {
			case "expired":
				db.tx.m.expiry = time.Now().Add(-time.Second)
			case "controller":
				db.tx.role = "mcpbench_controller"
			case "controller-session":
				db.tx.login = "mcpbench_controller"
			case "wrong-db":
				db.tx.db = "postgres"
			case "sealed":
				db.tx.m.phase = "agent_sealed"
			case "no-row":
				db.tx.queryErr = pgx.ErrNoRows
			}
			ran := false
			e := New(db).WithSession(context.Background(), a, billing.CreateDraft, func(billing.Session) error { ran = true; return nil })
			if e == nil || ran || db.tx.commits != 0 || db.tx.rollbacks != 1 {
				t.Fatalf("admitted %s: %v", what, e)
			}
			for _, q := range db.tx.queries {
				if strings.Contains(q, `"r_`) {
					t.Fatal("application SQL before authorization")
				}
			}
		})
	}
}
func TestCallbackRollbackUnknownAndRedaction(t *testing.T) {
	db, a := fixture()
	e := New(db).WithSession(context.Background(), a, "", func(billing.Session) error { return billing.Fail("invalid_arguments") })
	var be *billing.Error
	if !errors.As(e, &be) || be.Code != "invalid_arguments" || db.tx.rollbacks != 1 || db.tx.commits != 0 {
		t.Fatal(e)
	}
	db, a = fixture()
	db.tx.rollbackErr = errors.New("lost ACK secret")
	e = New(db).WithSession(context.Background(), a, "", func(billing.Session) error { return errors.New("SQL secret") })
	if !errors.As(e, &be) || !be.OutcomeUnknown || strings.Contains(e.Error(), "secret") {
		t.Fatal(e)
	}
}
func TestTransientClassification(t *testing.T) {
	for _, tc := range []struct {
		code  string
		retry bool
	}{{"40001", true}, {"40P01", true}, {"55P03", true}, {"23505", false}, {"23514", false}, {"42501", false}} {
		e := dbError(&pgconn.PgError{Code: tc.code, Message: "private SQL"}).(*billing.Error)
		if e.Retryable != tc.retry || strings.Contains(e.Message, "private") {
			t.Fatalf("classification %+v", e)
		}
	}
}

func TestSaveUsesOneTransactionAndTypedParameters(t *testing.T) {
	db, a := fixture()
	customer := []billing.Customer{{ID: "CUST-001", Active: true}}
	items := []billing.Item{{ID: "SVC-CONSULT", Active: true, Currency: "USD", Price: 12500}}
	draft, e := billing.BuildDraft(billing.CreateDraftArgs{CustomerID: "CUST-001", InvoiceDate: "2026-11-07", DueDate: "2026-12-07", Lines: []billing.CreateLine{{ItemID: "SVC-CONSULT", Quantity: 2}}}, customer, items, time.Now())
	if e != nil {
		t.Fatal(e)
	}
	e = New(db).WithSession(context.Background(), a, billing.CreateDraft, func(s billing.Session) error {
		if e := s.LockKey(context.Background(), a.IdempotencyKey); e != nil {
			return e
		}
		return s.SaveDraft(context.Background(), a.IdempotencyKey, strings.Repeat("0", 64), draft)
	})
	if e != nil {
		t.Fatal(e)
	}
	queries := db.tx.queries
	// The header insert is the fourth Exec, after two SETs and advisory lock.
	if _, ok := db.tx.args[3][2].(time.Time); !ok {
		t.Fatal("invoice date not encoded as PostgreSQL date")
	}
	if _, ok := db.tx.args[3][9].(time.Time); !ok {
		t.Fatal("creation time not encoded as timestamp")
	}
	if len(queries) != 8 || !strings.Contains(queries[4], "pg_advisory_xact_lock") || !strings.Contains(queries[5], `"invoices"`) || !strings.Contains(queries[6], `"invoice_lines"`) || !strings.Contains(queries[7], `"idempotency_records"`) || db.tx.commits != 1 {
		t.Fatalf("unexpected transaction queries %v", queries)
	}
}
func TestNoBeginForMalformedTrustedIdentity(t *testing.T) {
	db, a := fixture()
	a.RunID = "run; injected"
	e := New(db).WithSession(context.Background(), a, "", func(billing.Session) error { t.Fatal("callback"); return nil })
	if e == nil || db.begins != 0 {
		t.Fatal("malformed identity reached SQL")
	}
}

// catalogTx models only the SELECT filter/order/limit pipeline. It records the
// actual query so these offline checks also require filtering before the bound;
// it is not PostgreSQL runtime evidence.
type catalogTx struct {
	*fakeTx
	data [][]any
}

type catalogRows struct {
	pgx.Rows
	data [][]any
	pos  int
}

func (r *catalogRows) Next() bool { r.pos++; return r.pos <= len(r.data) }
func (r *catalogRows) Close()     {}
func (r *catalogRows) Err() error { return nil }
func (r *catalogRows) Scan(dest ...any) error {
	for i, value := range r.data[r.pos-1] {
		switch d := dest[i].(type) {
		case *string:
			*d = value.(string)
		case *bool:
			*d = value.(bool)
		case *int64:
			*d = value.(int64)
		default:
			panic("unexpected catalog column")
		}
	}
	return nil
}
func (tx *catalogTx) Query(_ context.Context, q string, _ ...any) (pgx.Rows, error) {
	tx.queries = append(tx.queries, q)
	data := [][]any{}
	for _, row := range tx.data {
		if !strings.Contains(q, " WHERE active") || row[len(row)-1].(bool) {
			data = append(data, row)
		}
	}
	sort.Slice(data, func(i, j int) bool { return data[i][0].(string) < data[j][0].(string) })
	if len(data) > 101 {
		data = data[:101]
	}
	return &catalogRows{data: data}, nil
}

type catalogDB struct{ tx *catalogTx }

func (db catalogDB) BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error) { return db.tx, nil }

func TestActiveListsFilterBeforeCap(t *testing.T) {
	for _, tool := range []string{billing.ListCustomers, billing.ListItems} {
		for _, tc := range []struct {
			name             string
			active, inactive int
			wantError        bool
		}{
			{"empty", 0, 0, false},
			{"inactive only beyond cap", 0, 150, false},
			{"mixed", 3, 2, false},
			{"inactive beyond cap", 3, 150, false},
			{"exact active cap", 100, 150, false},
			{"active overflow", 101, 150, true},
		} {
			t.Run(tool+"/"+tc.name, func(t *testing.T) {
				db, access := fixture()
				tx := &catalogTx{fakeTx: db.tx}
				// Descending input tests stable sorting. Inactive IDs sort before
				// active ones, exposing a LIMIT applied before the active filter.
				for n := tc.active + tc.inactive - 1; n >= 0; n-- {
					active := n >= tc.inactive
					id := fmt.Sprintf("REC-%03d", n)
					row := []any{id, "Synthetic", active}
					if tool == billing.ListItems {
						row = []any{id, "Synthetic", "hour", "USD", int64(12500), active}
					}
					tx.data = append(tx.data, row)
				}
				out, err := (billing.Service{Repo: New(catalogDB{tx})}).Call(context.Background(), access, tool, json.RawMessage(`{}`))
				idColumn := "customer_id"
				if tool == billing.ListItems {
					idColumn = "item_id"
				}
				query := tx.queries[len(tx.queries)-1]
				if !strings.HasSuffix(query, " WHERE active ORDER BY "+idColumn+" LIMIT 101") {
					t.Fatalf("active filter/order/cap missing: %s", query)
				}
				if tc.wantError {
					var be *billing.Error
					if !errors.As(err, &be) || be.Code != "tool_error" || out != nil || tx.commits != 0 {
						t.Fatalf("overflow result=%v error=%v commits=%d", out, err, tx.commits)
					}
					return
				}
				if err != nil {
					t.Fatal(err)
				}
				ids := []string{}
				switch result := out.(type) {
				case billing.CustomerOutput:
					if result.Customers == nil {
						t.Fatal("null list")
					}
					for _, record := range result.Customers {
						if !record.Active {
							t.Fatal("inactive customer exposed")
						}
						ids = append(ids, record.ID)
					}
				case billing.ItemOutput:
					if result.Items == nil {
						t.Fatal("null list")
					}
					for _, record := range result.Items {
						if !record.Active {
							t.Fatal("inactive item exposed")
						}
						ids = append(ids, record.ID)
					}
				default:
					t.Fatalf("unexpected result %T", out)
				}
				if len(ids) != tc.active || tx.commits != 1 {
					t.Fatalf("count=%d want=%d commits=%d", len(ids), tc.active, tx.commits)
				}
				for n, id := range ids {
					if want := fmt.Sprintf("REC-%03d", tc.inactive+n); id != want {
						t.Fatalf("id[%d]=%s want=%s", n, id, want)
					}
				}
			})
		}
	}
}

func TestValidationReadsRetainInactiveRecords(t *testing.T) {
	db, _ := fixture()
	tx := &catalogTx{fakeTx: db.tx, data: [][]any{{"CUST-001", "Synthetic", false}}}
	ctx, cancel := context.WithTimeout(context.Background(), billing.OperationLimit)
	defer cancel()
	s := &session{tx: tx, ctx: ctx, schema: "r_unit"}
	customers, err := s.Customers(ctx)
	if err != nil || len(customers) != 1 || customers[0].Active {
		t.Fatalf("inactive customer lost: %v %v", customers, err)
	}
	if strings.Contains(tx.queries[len(tx.queries)-1], "WHERE active") {
		t.Fatal("validation query filtered inactive customer")
	}
	tx.data = [][]any{{"SVC-CONSULT", "Synthetic", "hour", "USD", int64(12500), false}}
	items, err := s.Items(ctx)
	if err != nil || len(items) != 1 || items[0].Active {
		t.Fatalf("inactive item lost: %v %v", items, err)
	}
	if strings.Contains(tx.queries[len(tx.queries)-1], "WHERE active") {
		t.Fatal("validation query filtered inactive item")
	}
}
