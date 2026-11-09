package billing

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

func args() CreateDraftArgs {
	return CreateDraftArgs{"CUST-001", "2026-11-07", "2026-12-07", []CreateLine{{"SVC-CONSULT", 2}}}
}
func records() ([]Customer, []Item) {
	return []Customer{{"CUST-001", "Synthetic", true}}, []Item{{"SVC-CONSULT", "Consulting", "hour", "USD", 12500, true}}
}
func code(t *testing.T, e error, want string) {
	t.Helper()
	var b *Error
	if !errors.As(e, &b) || b.Code != want {
		t.Fatalf("error %v, want %s", e, want)
	}
}
func TestStrictArguments(t *testing.T) {
	raw, _ := json.Marshal(args())
	if _, e := ParseCreate(raw); e != nil {
		t.Fatal(e)
	}
	for _, bad := range []string{
		`null`, `[]`, `{"customer_id":"CUST-001","customer_id":"CUST-002"}`, string(raw) + ` {}`,
		strings.Replace(string(raw), `"quantity":2`, `"quantity":2.0`, 1), strings.Replace(string(raw), `"quantity":2`, `"quantity":2e0`, 1),
		strings.Replace(string(raw), `"quantity":2`, `"quantity":true`, 1), strings.Replace(string(raw), `"customer_id"`, `"Customer_ID"`, 1),
		strings.Replace(string(raw), `"customer_id":`, `"price":1,"customer_id":`, 1), strings.Replace(string(raw), `"item_id":`, `"item_id":"SVC-CONSULT","item_id":`, 1),
	} {
		if _, e := ParseCreate([]byte(bad)); e == nil {
			t.Fatalf("accepted %s", bad)
		}
	}
}
func TestDomainValidationAndPrices(t *testing.T) {
	c, i := records()
	out, e := BuildDraft(args(), c, i, time.Date(2026, 11, 7, 1, 2, 3, 123456789, time.UTC))
	if e != nil {
		t.Fatal(e)
	}
	if out.Invoice.Total != 25000 || out.Invoice.Tax != 0 || out.Lines[0].Price != 12500 || out.Lines[0].Number != 1 || out.Invoice.CreatedAt != "2026-11-07T01:02:03.123456Z" {
		t.Fatalf("bad draft %+v", out)
	}
	cases := []struct {
		name   string
		change func(*CreateDraftArgs)
		want   string
	}{
		{"bad date", func(a *CreateDraftArgs) { a.InvoiceDate = "2026-02-29" }, "invalid_arguments"},
		{"year zero", func(a *CreateDraftArgs) { a.InvoiceDate = "0000-01-01" }, "invalid_arguments"},
		{"due before", func(a *CreateDraftArgs) { a.DueDate = "2026-01-01" }, "invalid_arguments"},
		{"zero quantity", func(a *CreateDraftArgs) { a.Lines[0].Quantity = 0 }, "invalid_arguments"},
		{"large quantity", func(a *CreateDraftArgs) { a.Lines[0].Quantity = 1001 }, "invalid_arguments"},
		{"duplicate", func(a *CreateDraftArgs) { a.Lines = append(a.Lines, a.Lines[0]) }, "invalid_arguments"},
		{"unknown customer", func(a *CreateDraftArgs) { a.CustomerID = "UNKNOWN" }, "not_found"},
		{"unknown item", func(a *CreateDraftArgs) { a.Lines[0].ItemID = "UNKNOWN" }, "not_found"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			a := args()
			tc.change(&a)
			_, e := BuildDraft(a, c, i, time.Now())
			code(t, e, tc.want)
		})
	}
	c[0].Active = false
	_, e = BuildDraft(args(), c, i, time.Now())
	code(t, e, "inactive_record")
	c[0].Active = true
	i[0].Active = false
	_, e = BuildDraft(args(), c, i, time.Now())
	code(t, e, "inactive_record")
	i[0].Active = true
	i[0].Currency = "EUR"
	_, e = BuildDraft(args(), c, i, time.Now())
	code(t, e, "invalid_arguments")
	i[0].Currency = "USD"
	i[0].Price = MaxMoney/2 + 1
	_, e = BuildDraft(args(), c, i, time.Now())
	code(t, e, "invalid_arguments")
	a := args()
	a.Lines[0].Quantity = 1
	i[0].Price = MaxMoney
	i = append(i, Item{"SECOND", "second", "unit", "USD", 1, true})
	a.Lines = append(a.Lines, CreateLine{"SECOND", 1})
	_, e = BuildDraft(a, c, i, time.Now())
	code(t, e, "invalid_arguments")
	a.Lines = a.Lines[:1]
	out, e = BuildDraft(a, c, i, time.Now())
	if e != nil || out.Invoice.Total != MaxMoney {
		t.Fatalf("exact bound %v %+v", e, out)
	}
}
func TestPayloadHashPythonParity(t *testing.T) {
	python := os.Getenv("MCPBENCH_TEST_PYTHON")
	if python == "" {
		t.Skip("MCPBENCH_TEST_PYTHON not supplied; independent canonical parity UNRUN")
	}
	a := args()
	a.Lines = append(a.Lines, CreateLine{"SECOND", 1000})
	raw, _ := json.Marshal(a)
	cmd := exec.Command(python, "-c", `import json,sys; from contracts.validate import payload_hash; print(payload_hash(json.loads(sys.argv[1])))`, string(raw))
	cmd.Dir = "../.."
	cmd.Env = append(os.Environ(), "PYTHONDONTWRITEBYTECODE=1")
	out, e := cmd.CombinedOutput()
	if e != nil {
		t.Fatalf("python hash: %v %s", e, out)
	}
	hash, e := PayloadHash(a)
	if e != nil || hash != strings.TrimSpace(string(out)) {
		t.Fatalf("parity Go=%s Python=%s error=%v", hash, out, e)
	}
	a.Lines[0], a.Lines[1] = a.Lines[1], a.Lines[0]
	reversed, _ := PayloadHash(a)
	if reversed == hash {
		t.Fatal("line order lost")
	}
}

type memory struct {
	old           *DraftOutput
	hash          string
	scope         *Scope
	writes, locks int
	failure       error
}

func (m *memory) WithSession(ctx context.Context, a Access, tool string, fn func(Session) error) error {
	deadline, ok := ctx.Deadline()
	if !ok || time.Until(deadline) > OperationLimit {
		panic("missing operation deadline")
	}
	if e := fn(m); e != nil {
		return e
	}
	return m.failure
}
func (m *memory) AllowedTools() []string                                  { return []string{ListCustomers, ListItems, CreateDraft} }
func (m *memory) VerifierScope() *Scope                                   { return m.scope }
func (m *memory) Customers(context.Context) ([]Customer, error)           { c, _ := records(); return c, nil }
func (m *memory) Items(context.Context) ([]Item, error)                   { _, i := records(); return i, nil }
func (m *memory) ActiveCustomers(ctx context.Context) ([]Customer, error) { return m.Customers(ctx) }
func (m *memory) ActiveItems(ctx context.Context) ([]Item, error)         { return m.Items(ctx) }
func (m *memory) LockKey(context.Context, string) error                   { m.locks++; return nil }
func (m *memory) FindDraft(context.Context, string) (*DraftOutput, string, error) {
	return m.old, m.hash, nil
}
func (m *memory) SaveDraft(_ context.Context, _ string, h string, d DraftOutput) error {
	m.writes++
	m.hash = h
	m.old = &d
	return nil
}
func TestReplayConflictAndVerifier(t *testing.T) {
	m := &memory{}
	s := Service{m}
	a := Access{IdempotencyKey: "key-test"}
	raw, _ := json.Marshal(args())
	first, e := s.Call(context.Background(), a, CreateDraft, raw)
	if e != nil {
		t.Fatal(e)
	}
	again, e := s.Call(context.Background(), a, CreateDraft, raw)
	if e != nil || first.(DraftOutput).Invoice.ID != again.(DraftOutput).Invoice.ID || m.writes != 1 {
		t.Fatalf("replay: %v", e)
	}
	changed := args()
	changed.Lines[0].Quantity++
	conflict, _ := json.Marshal(changed)
	_, e = s.Call(context.Background(), a, CreateDraft, conflict)
	code(t, e, "idempotency_conflict")
	m.scope = &Scope{m.old.Invoice.ID, a.IdempotencyKey, m.hash}
	locks := m.locks
	_, e = s.Call(context.Background(), a, CreateDraft, raw)
	if e != nil {
		t.Fatal(e)
	}
	_, e = s.Call(context.Background(), a, CreateDraft, conflict)
	code(t, e, "idempotency_conflict")
	changed.CustomerID = "CUST-002"
	outside, _ := json.Marshal(changed)
	_, e = s.Call(context.Background(), a, CreateDraft, outside)
	code(t, e, "authorization_denied")
	m.old = nil
	_, e = s.Call(context.Background(), a, CreateDraft, raw)
	code(t, e, "verification_not_replayable")
	if m.writes != 1 || m.locks != locks {
		t.Fatal("verifier attempted write/lock")
	}
}
func TestNoResultWithoutCommitAck(t *testing.T) {
	m := &memory{failure: &Error{Code: "db_error", Message: "transaction settlement unknown", OutcomeUnknown: true}}
	raw, _ := json.Marshal(args())
	out, e := (Service{m}).Call(context.Background(), Access{IdempotencyKey: "key-test"}, CreateDraft, raw)
	if out != nil || e == nil {
		t.Fatal("success escaped failed commit")
	}
}

// Creation must use validation reads, which retain known inactive IDs, rather
// than the active-only list reads.
type validationMemory struct {
	memory
	customers []Customer
	items     []Item
}

func (m *validationMemory) WithSession(_ context.Context, _ Access, _ string, fn func(Session) error) error {
	return fn(m)
}
func (m *validationMemory) Customers(context.Context) ([]Customer, error) { return m.customers, nil }
func (m *validationMemory) Items(context.Context) ([]Item, error)         { return m.items, nil }
func (m *validationMemory) ActiveCustomers(context.Context) ([]Customer, error) {
	panic("create used list read")
}
func (m *validationMemory) ActiveItems(context.Context) ([]Item, error) {
	panic("create used list read")
}

func TestCreateRetainsInactiveVsMissingClassification(t *testing.T) {
	for _, tc := range []struct {
		name           string
		customer, item string
		want           string
	}{
		{"inactive customer", "inactive", "active", "inactive_record"},
		{"missing customer", "missing", "active", "not_found"},
		{"inactive item", "active", "inactive", "inactive_record"},
		{"missing item", "active", "missing", "not_found"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c, i := records()
			if tc.customer == "inactive" {
				c[0].Active = false
			}
			if tc.customer == "missing" {
				c = nil
			}
			if tc.item == "inactive" {
				i[0].Active = false
			}
			if tc.item == "missing" {
				i = nil
			}
			m := &validationMemory{customers: c, items: i}
			raw, _ := json.Marshal(args())
			out, err := (Service{Repo: m}).Call(context.Background(), Access{IdempotencyKey: "key-test"}, CreateDraft, raw)
			code(t, err, tc.want)
			if out != nil || m.writes != 0 {
				t.Fatal("invalid draft saved or returned")
			}
		})
	}
}
