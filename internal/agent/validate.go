package agent

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/google/jsonschema-go/jsonschema"
	"io"
	"mcpbench/internal/ollama"
	"regexp"
	"strings"
	"sync"
	"time"
)

//go:embed schema.json
var schemaBytes []byte
var invalid = errors.New("invalid contract document")

// StrictJSON rejects duplicate keys, noninteger numeric lexical forms, invalid
// UTF-8/scalars, trailing values, and documents/nesting beyond the wire limits.
func StrictJSON(b []byte) (any, error) { return ollama.StrictJSON(b) }

var resolvedSchemas sync.Map

func Validate(kind string, b []byte) error {
	v, e := StrictJSON(b)
	if e != nil {
		return invalid
	}
	cached, ok := resolvedSchemas.Load(kind)
	if !ok {
		var root map[string]any
		if json.Unmarshal(schemaBytes, &root) != nil {
			return invalid
		}
		root["$ref"] = "#/$defs/" + kind
		raw, _ := json.Marshal(root)
		var s jsonschema.Schema
		if json.Unmarshal(raw, &s) != nil {
			return invalid
		}
		r, e := s.Resolve(nil)
		if e != nil {
			return fmt.Errorf("schema unavailable: %w", e)
		}
		resolvedSchemas.Store(kind, r)
		cached = r
	}
	if cached.(*jsonschema.Resolved).Validate(v) != nil {
		return invalid
	}
	return nil
}
func Decode(kind string, b []byte, out any) error {
	if e := Validate(kind, b); e != nil {
		return e
	}
	return json.Unmarshal(b, out)
}

var businessID = regexp.MustCompile(`^[A-Z][A-Z0-9_-]{0,63}$`)

func ValidateArguments(name string, b []byte) error {
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	for {
		t, e := d.Token()
		if e == io.EOF {
			break
		}
		if e != nil {
			return invalid
		}
		if n, ok := t.(json.Number); ok && strings.ContainsAny(string(n), ".eE") {
			return invalid
		}
	}
	kind := "EmptyArgs"
	if name == "billing_create_draft_invoice" {
		kind = "CreateDraftArgs"
	} else if name != "billing_list_customers" && name != "billing_list_items" {
		return invalid
	}
	if e := Validate(kind, b); e != nil {
		return e
	}
	if kind == "EmptyArgs" {
		return nil
	}
	var a struct {
		CustomerID  string `json:"customer_id"`
		InvoiceDate string `json:"invoice_date"`
		DueDate     string `json:"due_date"`
		Lines       []struct {
			ItemID   string `json:"item_id"`
			Quantity int    `json:"quantity"`
		} `json:"lines"`
	}
	if json.Unmarshal(b, &a) != nil {
		return invalid
	}
	i, e := time.Parse("2006-01-02", a.InvoiceDate)
	if e != nil || i.Year() < 1 {
		return invalid
	}
	due, e := time.Parse("2006-01-02", a.DueDate)
	if e != nil || due.Year() < 1 || due.Before(i) || !businessID.MatchString(a.CustomerID) {
		return invalid
	}
	seen := map[string]bool{}
	for _, l := range a.Lines {
		if seen[l.ItemID] || !businessID.MatchString(l.ItemID) {
			return invalid
		}
		seen[l.ItemID] = true
	}
	return nil
}
func validateAuth(a AuthInput, run, attempt, mode string) error {
	b, _ := json.Marshal(a)
	if Validate("AuthInput", b) != nil || a.RunID != run || a.AttemptID != attempt || a.Mode != mode {
		return invalid
	}
	return nil
}
