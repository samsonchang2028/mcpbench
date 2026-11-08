// Package billing implements the three-tool synthetic draft-invoice domain.
package billing

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"regexp"
	"time"
	"unicode/utf8"
)

const (
	ListCustomers        = "billing_list_customers"
	ListItems            = "billing_list_items"
	CreateDraft          = "billing_create_draft_invoice"
	MaxMoney       int64 = 9007199254740991
	OperationLimit       = 5 * time.Second
)

var Identifier = regexp.MustCompile(`^[a-z][a-z0-9-]{0,63}$`)
var BusinessID = regexp.MustCompile(`^[A-Z][A-Z0-9_-]{0,63}$`)

// Error is a bounded ToolError. OutcomeUnknown is private settlement metadata;
// adapters must retain it in trusted diagnostics, never report rollback/success.
type Error struct {
	Code           string `json:"code"`
	Message        string `json:"message"`
	Retryable      bool   `json:"retryable"`
	OutcomeUnknown bool   `json:"-"`
}

func (e *Error) Error() string { return e.Code + ": " + e.Message }
func Fail(code string) *Error  { return &Error{Code: code, Message: code} }

// Access is populated only by the trusted HTTP/auth adapter, never tool arguments.
type Access struct{ RunID, AttemptID, IdempotencyKey, Capability string }
type Scope struct {
	InvoiceID           string `json:"invoice_id"`
	IdempotencyKey      string `json:"idempotency_key"`
	OriginalRequestHash string `json:"original_request_hash"`
}
type Customer struct {
	ID     string `json:"customer_id"`
	Name   string `json:"name"`
	Active bool   `json:"active"`
}
type Item struct {
	ID       string `json:"item_id"`
	Name     string `json:"name"`
	Unit     string `json:"unit"`
	Currency string `json:"currency"`
	Price    int64  `json:"unit_price_cents"`
	Active   bool   `json:"active"`
}
type CreateLine struct {
	ItemID   string `json:"item_id"`
	Quantity int64  `json:"quantity"`
}
type CreateDraftArgs struct {
	CustomerID  string       `json:"customer_id"`
	InvoiceDate string       `json:"invoice_date"`
	DueDate     string       `json:"due_date"`
	Lines       []CreateLine `json:"lines"`
}
type Invoice struct {
	ID          string `json:"invoice_id"`
	CustomerID  string `json:"customer_id"`
	InvoiceDate string `json:"invoice_date"`
	DueDate     string `json:"due_date"`
	Currency    string `json:"currency"`
	Status      string `json:"status"`
	Subtotal    int64  `json:"subtotal_cents"`
	Tax         int64  `json:"tax_cents"`
	Total       int64  `json:"total_cents"`
	CreatedAt   string `json:"created_at"`
}
type InvoiceLine struct {
	ID        string `json:"line_id"`
	InvoiceID string `json:"invoice_id"`
	ItemID    string `json:"item_id"`
	Quantity  int64  `json:"quantity"`
	Price     int64  `json:"unit_price_cents"`
	Total     int64  `json:"line_total_cents"`
	Number    int    `json:"line_number"`
}
type DraftOutput struct {
	Invoice Invoice       `json:"invoice"`
	Lines   []InvoiceLine `json:"lines"`
}
type CustomerOutput struct {
	Customers []Customer `json:"customers"`
}
type ItemOutput struct {
	Items []Item `json:"items"`
}

// Repository must authorize under the registry shared lock and commit positively
// before returning nil. Session is valid only inside the callback.
type Repository interface {
	WithSession(context.Context, Access, string, func(Session) error) error
}
type Session interface {
	AllowedTools() []string
	VerifierScope() *Scope
	Customers(context.Context) ([]Customer, error)
	Items(context.Context) ([]Item, error)
	// LockKey serializes execution creates for this trusted run/key until tx end.
	LockKey(context.Context, string) error
	FindDraft(context.Context, string) (*DraftOutput, string, error)
	SaveDraft(context.Context, string, string, DraftOutput) error
}
type Service struct{ Repo Repository }

func (s Service) Authorize(ctx context.Context, a Access) (tools []string, err error) {
	ctx, cancel := context.WithTimeout(ctx, OperationLimit)
	defer cancel()
	err = s.Repo.WithSession(ctx, a, "", func(tx Session) error { tools = append([]string(nil), tx.AllowedTools()...); return nil })
	if err != nil {
		tools = nil
	}
	return
}

// Call returns a schema-shaped result only after acknowledged transaction commit.
// There are no automatic retries; the caller owns the single task retry budget.
func (s Service) Call(ctx context.Context, a Access, tool string, raw json.RawMessage) (result any, err error) {
	ctx, cancel := context.WithTimeout(ctx, OperationLimit)
	defer cancel()
	err = s.Repo.WithSession(ctx, a, tool, func(tx Session) error {
		switch tool {
		case ListCustomers:
			if err := emptyArgs(raw); err != nil {
				return err
			}
			v, e := tx.Customers(ctx)
			if e != nil {
				return e
			}
			if v == nil {
				v = []Customer{}
			}
			result = CustomerOutput{v}
			return nil
		case ListItems:
			if err := emptyArgs(raw); err != nil {
				return err
			}
			v, e := tx.Items(ctx)
			if e != nil {
				return e
			}
			if v == nil {
				v = []Item{}
			}
			result = ItemOutput{v}
			return nil
		case CreateDraft:
			args, e := ParseCreate(raw)
			if e != nil {
				return e
			}
			if !Identifier.MatchString(a.IdempotencyKey) {
				return Fail("authorization_denied")
			}
			hash, e := PayloadHash(args)
			if e != nil {
				return e
			}
			if tx.VerifierScope() == nil {
				if e = tx.LockKey(ctx, a.IdempotencyKey); e != nil {
					return e
				}
			}
			old, oldHash, e := tx.FindDraft(ctx, a.IdempotencyKey)
			if e != nil {
				return e
			}
			if scope := tx.VerifierScope(); scope != nil {
				if scope.IdempotencyKey != a.IdempotencyKey {
					return Fail("authorization_denied")
				}
				if old == nil {
					return Fail("verification_not_replayable")
				}
				if old.Invoice.ID != scope.InvoiceID || oldHash != scope.OriginalRequestHash {
					return Fail("authorization_denied")
				}
				original := Arguments(*old)
				oh, e := PayloadHash(original)
				if e != nil || oh != oldHash {
					return Fail("verification_not_replayable")
				}
				if hash == oldHash {
					result = *old
					return nil
				}
				original.Lines = append([]CreateLine(nil), original.Lines...)
				if original.Lines[0].Quantity == 1000 {
					original.Lines[0].Quantity--
				} else {
					original.Lines[0].Quantity++
				}
				conflict, _ := PayloadHash(original)
				if hash != conflict {
					return Fail("authorization_denied")
				}
				return Fail("idempotency_conflict")
			}
			if old != nil {
				if hash != oldHash {
					return Fail("idempotency_conflict")
				}
				result = *old
				return nil
			}
			customers, e := tx.Customers(ctx)
			if e != nil {
				return e
			}
			items, e := tx.Items(ctx)
			if e != nil {
				return e
			}
			out, e := BuildDraft(args, customers, items, time.Now().UTC())
			if e != nil {
				return e
			}
			if e = tx.SaveDraft(ctx, a.IdempotencyKey, hash, out); e != nil {
				return e
			}
			result = out
			return nil
		default:
			return Fail("authorization_denied")
		}
	})
	if err != nil {
		result = nil
	}
	return
}
func Arguments(d DraftOutput) CreateDraftArgs {
	a := CreateDraftArgs{CustomerID: d.Invoice.CustomerID, InvoiceDate: d.Invoice.InvoiceDate, DueDate: d.Invoice.DueDate, Lines: []CreateLine{}}
	for _, l := range d.Lines {
		a.Lines = append(a.Lines, CreateLine{l.ItemID, l.Quantity})
	}
	return a
}
func Validate(a CreateDraftArgs) error {
	if !BusinessID.MatchString(a.CustomerID) || len(a.Lines) < 1 || len(a.Lines) > 10 {
		return Fail("invalid_arguments")
	}
	for _, d := range []string{a.InvoiceDate, a.DueDate} {
		t, e := time.Parse("2006-01-02", d)
		if e != nil || len(d) != 10 || t.Year() < 1 || t.Format("2006-01-02") != d {
			return Fail("invalid_arguments")
		}
	}
	if a.DueDate < a.InvoiceDate {
		return Fail("invalid_arguments")
	}
	seen := map[string]bool{}
	for _, l := range a.Lines {
		if !BusinessID.MatchString(l.ItemID) || l.Quantity < 1 || l.Quantity > 1000 || seen[l.ItemID] {
			return Fail("invalid_arguments")
		}
		seen[l.ItemID] = true
	}
	return nil
}
func BuildDraft(a CreateDraftArgs, customers []Customer, items []Item, now time.Time) (DraftOutput, error) {
	var out DraftOutput
	if now.Year() < 1 || now.Year() > 9999 {
		return out, Fail("invalid_arguments")
	}
	if e := Validate(a); e != nil {
		return out, e
	}
	found := false
	for _, c := range customers {
		if c.ID == a.CustomerID {
			found = true
			if !c.Active {
				return out, Fail("inactive_record")
			}
		}
	}
	if !found {
		return out, Fail("not_found")
	}
	id, e := newID("INV-")
	if e != nil {
		return out, Fail("tool_error")
	}
	out.Invoice = Invoice{ID: id, CustomerID: a.CustomerID, InvoiceDate: a.InvoiceDate, DueDate: a.DueDate, Currency: "USD", Status: "draft", CreatedAt: now.UTC().Truncate(time.Microsecond).Format("2006-01-02T15:04:05.999999Z")}
	out.Lines = []InvoiceLine{}
	for i, l := range a.Lines {
		var item *Item
		for j := range items {
			if items[j].ID == l.ItemID {
				item = &items[j]
				break
			}
		}
		if item == nil {
			return DraftOutput{}, Fail("not_found")
		}
		if !item.Active {
			return DraftOutput{}, Fail("inactive_record")
		}
		if item.Currency != "USD" || item.Price < 0 || item.Price > MaxMoney/l.Quantity {
			return DraftOutput{}, Fail("invalid_arguments")
		}
		total := item.Price * l.Quantity
		if out.Invoice.Subtotal > MaxMoney-total {
			return DraftOutput{}, Fail("invalid_arguments")
		}
		out.Invoice.Subtotal += total
		lineID, e := newID("LINE-")
		if e != nil {
			return DraftOutput{}, Fail("tool_error")
		}
		out.Lines = append(out.Lines, InvoiceLine{lineID, id, l.ItemID, l.Quantity, item.Price, total, i + 1})
	}
	out.Invoice.Total = out.Invoice.Subtotal
	return out, nil
}
func newID(prefix string) (string, error) {
	var b [16]byte
	_, e := rand.Read(b[:])
	return prefix + fmt.Sprintf("%X", b), e
}

// PayloadHash exactly matches contracts.validate.payload_hash: ASCII-only values,
// sorted object keys, integer lexical quantities, original line ordering.
func PayloadHash(a CreateDraftArgs) (string, error) {
	if e := Validate(a); e != nil {
		return "", e
	}
	lines := make([]map[string]any, len(a.Lines))
	for i, l := range a.Lines {
		lines[i] = map[string]any{"item_id": l.ItemID, "quantity": l.Quantity}
	}
	b, e := json.Marshal(map[string]any{"arguments": map[string]any{"customer_id": a.CustomerID, "due_date": a.DueDate, "invoice_date": a.InvoiceDate, "lines": lines}, "tool_id": CreateDraft})
	if e != nil {
		return "", e
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:]), nil
}

func emptyArgs(raw []byte) error {
	v, e := decode(raw)
	if e != nil {
		return e
	}
	m, ok := v.(map[string]any)
	if !ok || len(m) != 0 {
		return Fail("invalid_arguments")
	}
	return nil
}
func ParseCreate(raw []byte) (CreateDraftArgs, error) {
	var a CreateDraftArgs
	v, e := decode(raw)
	if e != nil {
		return a, e
	}
	m, ok := v.(map[string]any)
	if !ok || !keys(m, "customer_id", "invoice_date", "due_date", "lines") {
		return a, Fail("invalid_arguments")
	}
	a.CustomerID, _ = m["customer_id"].(string)
	a.InvoiceDate, _ = m["invoice_date"].(string)
	a.DueDate, _ = m["due_date"].(string)
	ls, ok := m["lines"].([]any)
	if !ok {
		return a, Fail("invalid_arguments")
	}
	for _, v := range ls {
		l, ok := v.(map[string]any)
		if !ok || !keys(l, "item_id", "quantity") {
			return a, Fail("invalid_arguments")
		}
		id, _ := l["item_id"].(string)
		n, ok := l["quantity"].(json.Number)
		if !ok {
			return a, Fail("invalid_arguments")
		}
		q, e := n.Int64()
		if e != nil {
			return a, Fail("invalid_arguments")
		}
		a.Lines = append(a.Lines, CreateLine{id, q})
	}
	return a, Validate(a)
}
func keys(m map[string]any, ks ...string) bool {
	if len(m) != len(ks) {
		return false
	}
	for _, k := range ks {
		if _, ok := m[k]; !ok {
			return false
		}
	}
	return true
}
func decode(raw []byte) (any, error) {
	if len(raw) > 1<<20 || !utf8.Valid(raw) {
		return nil, Fail("invalid_arguments")
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	v, e := value(d, 0)
	if e != nil {
		return nil, Fail("invalid_arguments")
	}
	if _, e = d.Token(); !errors.Is(e, io.EOF) {
		return nil, Fail("invalid_arguments")
	}
	return v, nil
}
func value(d *json.Decoder, depth int) (any, error) {
	if depth > 16 {
		return nil, errors.New("depth")
	}
	t, e := d.Token()
	if e != nil {
		return nil, e
	}
	switch t {
	case json.Delim('{'):
		m := map[string]any{}
		for d.More() {
			k, e := d.Token()
			if e != nil {
				return nil, e
			}
			s, ok := k.(string)
			if !ok {
				return nil, errors.New("key")
			}
			if _, ok = m[s]; ok {
				return nil, errors.New("duplicate")
			}
			v, e := value(d, depth+1)
			if e != nil {
				return nil, e
			}
			m[s] = v
		}
		_, e = d.Token()
		return m, e
	case json.Delim('['):
		a := []any{}
		for d.More() {
			v, e := value(d, depth+1)
			if e != nil {
				return nil, e
			}
			a = append(a, v)
		}
		_, e = d.Token()
		return a, e
	}
	if _, ok := t.(json.Delim); ok {
		return nil, errors.New("delimiter")
	}
	return t, nil
}
