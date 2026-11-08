// Package store implements the least-privilege PostgreSQL billing repository.
package store

import (
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"regexp"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"mcpbench/internal/billing"
)

type Beginner interface {
	BeginTx(context.Context, pgx.TxOptions) (pgx.Tx, error)
}
type Store struct{ db Beginner }

// New never opens a connection. Supply only a dedicated mcpbench_service source.
func New(db Beginner) *Store { return &Store{db: db} }

var hexDigest = regexp.MustCompile(`^[0-9a-f]{64}$`)
var schemaPattern = regexp.MustCompile(`^r_[0-9a-f]{32}$`)

type mapping struct {
	run, attempt, tenant, principal, schema, phase, workflow string
	tools                                                    []string
	generation                                               int
	expiry                                                   time.Time
	agent, verifier                                          *string
	scope                                                    []byte
}
type session struct {
	tx     pgx.Tx
	ctx    context.Context
	schema string
	tools  []string
	scope  *billing.Scope
	run    string
}

func (s *session) AllowedTools() []string { return append([]string(nil), s.tools...) }
func (s *session) VerifierScope() *billing.Scope {
	if s.scope == nil {
		return nil
	}
	v := *s.scope
	return &v
}
func SchemaName(run string) string {
	sum := sha256.Sum256([]byte(run))
	return "r_" + hex.EncodeToString(sum[:])[:32]
}
func knownTool(t string) bool {
	switch t {
	case billing.ListCustomers, billing.ListItems, billing.CreateDraft, "billing_get_customer", "billing_list_projects", "billing_get_project", "billing_list_timesheets", "billing_get_timesheet", "billing_list_invoices", "billing_get_invoice":
		return true
	}
	return false
}
func authorize(m mapping, a billing.Access, tool string, now time.Time) (*billing.Scope, error) {
	deny := func() (*billing.Scope, error) { return nil, billing.Fail("authorization_denied") }
	if !billing.Identifier.MatchString(a.RunID) || !billing.Identifier.MatchString(a.AttemptID) || !hexDigest.MatchString(a.Capability) || m.run != a.RunID || m.attempt != a.AttemptID || !billing.BusinessID.MatchString(m.tenant) || !schemaPattern.MatchString(m.schema) || m.schema != SchemaName(a.RunID) || !now.Before(m.expiry) {
		return deny()
	}
	if m.principal != "billing-reader" && m.principal != "billing-drafter" {
		return deny()
	}
	if m.workflow != "draft_invoice" && m.workflow != "read_only" {
		return deny()
	}
	if len(m.tools) < 1 || len(m.tools) > 10 {
		return deny()
	}
	seen := map[string]bool{}
	for _, t := range m.tools {
		if seen[t] || !knownTool(t) {
			return deny()
		}
		seen[t] = true
	}
	if seen[billing.CreateDraft] && (m.principal == "billing-reader" || m.workflow == "read_only") {
		return deny()
	}
	if tool != "" && !seen[tool] {
		return deny()
	}
	if tool == billing.CreateDraft && (m.principal != "billing-drafter" || m.workflow != "draft_invoice") {
		return deny()
	}
	sum := sha256.Sum256([]byte(a.Capability))
	digest := hex.EncodeToString(sum[:])
	match := func(stored *string) bool {
		return stored != nil && hexDigest.MatchString(*stored) && subtle.ConstantTimeCompare([]byte(*stored), []byte(digest)) == 1
	}
	if m.phase == "executing" && m.generation == 0 && match(m.agent) && m.verifier == nil && len(m.scope) == 0 {
		return nil, nil
	}
	if m.phase != "verifying" || m.generation != 1 || !match(m.verifier) || m.agent != nil || m.workflow != "draft_invoice" || m.principal != "billing-drafter" {
		return deny()
	}
	if tool != "" && tool != billing.CreateDraft {
		return deny()
	}
	var scope billing.Scope
	var fields map[string]json.RawMessage
	if json.Unmarshal(m.scope, &fields) != nil || len(fields) != 3 || fields["invoice_id"] == nil || fields["idempotency_key"] == nil || fields["original_request_hash"] == nil || json.Unmarshal(m.scope, &scope) != nil || !billing.BusinessID.MatchString(scope.InvoiceID) || !billing.Identifier.MatchString(scope.IdempotencyKey) || !hexDigest.MatchString(scope.OriginalRequestHash) || scope.IdempotencyKey != a.IdempotencyKey {
		return deny()
	}
	return &scope, nil
}
func (s *Store) WithSession(parent context.Context, a billing.Access, tool string, fn func(billing.Session) error) error {
	ctx, cancel := context.WithTimeout(parent, billing.OperationLimit)
	defer cancel()
	if !billing.Identifier.MatchString(a.RunID) || !billing.Identifier.MatchString(a.AttemptID) || !hexDigest.MatchString(a.Capability) {
		return billing.Fail("authorization_denied")
	}
	tx, e := s.db.BeginTx(ctx, pgx.TxOptions{IsoLevel: pgx.ReadCommitted})
	if e != nil {
		return dbError(e)
	}
	settled := false
	// Rollback uses the same bounded operation context; no detached cleanup writes.
	// pgx closes a broken connection if rollback cannot be acknowledged.
	defer func() {
		if !settled {
			_ = tx.Rollback(ctx)
		}
	}()
	abort := func(cause error) error {
		e := tx.Rollback(ctx)
		settled = true
		if e != nil {
			return unknown()
		}
		return normalize(cause)
	}
	if _, e = tx.Exec(ctx, "SET LOCAL statement_timeout = '4000ms'"); e != nil {
		return abort(e)
	}
	if _, e = tx.Exec(ctx, "SET LOCAL lock_timeout = '1000ms'"); e != nil {
		return abort(e)
	}
	var role, login, db string
	if e = tx.QueryRow(ctx, "SELECT current_user, session_user, current_database()").Scan(&role, &login, &db); e != nil {
		return abort(e)
	}
	if role != "mcpbench_service" || login != "mcpbench_service" || db != "mcpbench" {
		return abort(billing.Fail("authorization_denied"))
	}
	var m mapping
	// This is the first application/control lock. READ COMMITTED rechecks the
	// latest row after a queued controller update finishes.
	e = tx.QueryRow(ctx, `SELECT run_id,attempt_id,tenant_id,principal_id,allowed_tools,schema_name,phase,generation,not_after,agent_token_sha256,verifier_token_sha256,verifier_scope,workflow_kind FROM bench_control.run_registry WHERE run_id=$1 FOR SHARE`, a.RunID).Scan(&m.run, &m.attempt, &m.tenant, &m.principal, &m.tools, &m.schema, &m.phase, &m.generation, &m.expiry, &m.agent, &m.verifier, &m.scope, &m.workflow)
	if errors.Is(e, pgx.ErrNoRows) {
		return abort(billing.Fail("authorization_denied"))
	}
	if e != nil {
		return abort(e)
	}
	scope, e := authorize(m, a, tool, time.Now().UTC())
	if e != nil {
		return abort(e)
	}
	tools := m.tools
	if scope != nil {
		tools = []string{billing.CreateDraft}
	}
	ss := &session{tx: tx, ctx: ctx, schema: m.schema, run: m.run, tools: tools, scope: scope}
	if e = fn(ss); e != nil {
		return abort(e)
	}
	if e = ctx.Err(); e != nil {
		return abort(e)
	}
	e = tx.Commit(ctx)
	settled = true
	// Any absent COMMIT acknowledgment is conservatively unknown. Never expose
	// the callback's draft on this path, including cancellation or lost connection.
	if e != nil {
		return unknown()
	}
	if ctx.Err() != nil {
		return unknown()
	}
	return nil
}
func unknown() *billing.Error {
	return &billing.Error{Code: "db_error", Message: "transaction settlement unknown", OutcomeUnknown: true}
}
func normalize(e error) error {
	var be *billing.Error
	if errors.As(e, &be) {
		return be
	}
	return dbError(e)
}
func dbError(e error) error {
	if errors.Is(e, context.DeadlineExceeded) || errors.Is(e, context.Canceled) {
		return &billing.Error{Code: "tool_timeout", Message: "operation cancelled or timed out", Retryable: errors.Is(e, context.DeadlineExceeded)}
	}
	var pe *pgconn.PgError
	if errors.As(e, &pe) {
		return &billing.Error{Code: "db_error", Message: "database operation failed", Retryable: pe.Code == "40001" || pe.Code == "40P01" || pe.Code == "55P03" || pe.Code == "57014"}
	}
	return &billing.Error{Code: "db_error", Message: "database operation failed"}
}
func (s *session) table(name string) string { return pgx.Identifier{s.schema, name}.Sanitize() }
func (s *session) Customers(ctx context.Context) ([]billing.Customer, error) {
	ctx = s.ctx
	rows, e := s.tx.Query(ctx, "SELECT customer_id,name,active FROM "+s.table("customers")+" ORDER BY customer_id LIMIT 101")
	if e != nil {
		return nil, normalize(e)
	}
	defer rows.Close()
	out := []billing.Customer{}
	for rows.Next() {
		var v billing.Customer
		if e = rows.Scan(&v.ID, &v.Name, &v.Active); e != nil {
			return nil, normalize(e)
		}
		out = append(out, v)
	}
	if rows.Err() != nil {
		return nil, normalize(rows.Err())
	}
	if len(out) > 100 {
		return nil, billing.Fail("tool_error")
	}
	return out, nil
}
func (s *session) Items(ctx context.Context) ([]billing.Item, error) {
	ctx = s.ctx
	rows, e := s.tx.Query(ctx, "SELECT item_id,name,unit,currency,unit_price_cents,active FROM "+s.table("items")+" ORDER BY item_id LIMIT 101")
	if e != nil {
		return nil, normalize(e)
	}
	defer rows.Close()
	out := []billing.Item{}
	for rows.Next() {
		var v billing.Item
		if e = rows.Scan(&v.ID, &v.Name, &v.Unit, &v.Currency, &v.Price, &v.Active); e != nil {
			return nil, normalize(e)
		}
		out = append(out, v)
	}
	if rows.Err() != nil {
		return nil, normalize(rows.Err())
	}
	if len(out) > 100 {
		return nil, billing.Fail("tool_error")
	}
	return out, nil
}
func (s *session) LockKey(ctx context.Context, key string) error {
	ctx = s.ctx
	if s.scope != nil {
		return billing.Fail("authorization_denied")
	}
	_, e := s.tx.Exec(ctx, "SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended($1,0))", s.run+":"+key)
	return normalizeNil(e)
}
func normalizeNil(e error) error {
	if e == nil {
		return nil
	}
	return normalize(e)
}
func (s *session) FindDraft(ctx context.Context, key string) (*billing.DraftOutput, string, error) {
	ctx = s.ctx
	var hash, id string
	e := s.tx.QueryRow(ctx, "SELECT request_hash,invoice_id FROM "+s.table("idempotency_records")+" WHERE idempotency_key=$1", key).Scan(&hash, &id)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, "", nil
	}
	if e != nil {
		return nil, "", normalize(e)
	}
	var d billing.DraftOutput
	var invoiceDate, dueDate, created time.Time
	e = s.tx.QueryRow(ctx, "SELECT invoice_id,customer_id,invoice_date,due_date,currency,status,subtotal_cents,tax_cents,total_cents,created_at FROM "+s.table("invoices")+" WHERE invoice_id=$1", id).Scan(&d.Invoice.ID, &d.Invoice.CustomerID, &invoiceDate, &dueDate, &d.Invoice.Currency, &d.Invoice.Status, &d.Invoice.Subtotal, &d.Invoice.Tax, &d.Invoice.Total, &created)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, "", billing.Fail("verification_not_replayable")
	}
	if e != nil {
		return nil, "", normalize(e)
	}
	d.Invoice.InvoiceDate = invoiceDate.Format("2006-01-02")
	d.Invoice.DueDate = dueDate.Format("2006-01-02")
	d.Invoice.CreatedAt = created.UTC().Format("2006-01-02T15:04:05.999999Z")
	rows, e := s.tx.Query(ctx, "SELECT line_id,invoice_id,item_id,quantity,unit_price_cents,line_total_cents,line_number FROM "+s.table("invoice_lines")+" WHERE invoice_id=$1 ORDER BY line_number", id)
	if e != nil {
		return nil, "", normalize(e)
	}
	defer rows.Close()
	d.Lines = []billing.InvoiceLine{}
	for rows.Next() {
		var l billing.InvoiceLine
		if e = rows.Scan(&l.ID, &l.InvoiceID, &l.ItemID, &l.Quantity, &l.Price, &l.Total, &l.Number); e != nil {
			return nil, "", normalize(e)
		}
		d.Lines = append(d.Lines, l)
	}
	if rows.Err() != nil {
		return nil, "", normalize(rows.Err())
	}
	if len(d.Lines) < 1 || len(d.Lines) > 10 {
		return nil, "", billing.Fail("verification_not_replayable")
	}
	return &d, hash, nil
}
func (s *session) SaveDraft(ctx context.Context, key, hash string, d billing.DraftOutput) error {
	ctx = s.ctx
	if s.scope != nil {
		return billing.Fail("authorization_denied")
	}
	h := d.Invoice
	invoiceDate, e := time.Parse("2006-01-02", h.InvoiceDate)
	if e != nil {
		return billing.Fail("invalid_arguments")
	}
	dueDate, e := time.Parse("2006-01-02", h.DueDate)
	if e != nil {
		return billing.Fail("invalid_arguments")
	}
	created, e := time.Parse(time.RFC3339Nano, h.CreatedAt)
	if e != nil {
		return billing.Fail("invalid_arguments")
	}
	_, e = s.tx.Exec(ctx, "INSERT INTO "+s.table("invoices")+" (invoice_id,customer_id,invoice_date,due_date,currency,status,subtotal_cents,tax_cents,total_cents,created_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)", h.ID, h.CustomerID, invoiceDate, dueDate, h.Currency, h.Status, h.Subtotal, h.Tax, h.Total, created)
	if e != nil {
		return normalize(e)
	}
	for _, l := range d.Lines {
		_, e = s.tx.Exec(ctx, "INSERT INTO "+s.table("invoice_lines")+" (line_id,invoice_id,item_id,quantity,unit_price_cents,line_total_cents,line_number) VALUES ($1,$2,$3,$4,$5,$6,$7)", l.ID, l.InvoiceID, l.ItemID, l.Quantity, l.Price, l.Total, l.Number)
		if e != nil {
			return normalize(e)
		}
	}
	_, e = s.tx.Exec(ctx, "INSERT INTO "+s.table("idempotency_records")+" (idempotency_key,request_hash,invoice_id) VALUES ($1,$2,$3)", key, hash, h.ID)
	return normalizeNil(e)
}

var _ billing.Repository = (*Store)(nil)
