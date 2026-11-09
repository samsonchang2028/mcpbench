package mcp

import (
	_ "embed"
	"encoding/json"
	"errors"
	"strings"
	"sync"

	"github.com/google/jsonschema-go/jsonschema"
	"mcpbench/internal/agent"
)

// The frozen local contracts are embedded so production never needs Python,
// schema-network access, or a working-directory-dependent contract path.
//
//go:embed schema.json
var schemaBytes []byte

//go:embed catalog.json
var catalogBytes []byte
var invalid = errors.New("invalid MCP contract")
var schemas sync.Map

func validate(kind string, b []byte) error {
	v, err := agent.StrictJSON(b)
	if err != nil {
		return invalid
	}
	cached, ok := schemas.Load(kind)
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
		r, err := s.Resolve(nil)
		if err != nil {
			return invalid
		}
		cached, _ = schemas.LoadOrStore(kind, r)
	}
	if cached.(*jsonschema.Resolved).Validate(v) != nil {
		return invalid
	}
	return nil
}

// resolved expands only frozen local references. No external references or
// recursive schemas are accepted; advertised schemas are complete object trees.
func resolved(ref string) (map[string]any, error) {
	var root map[string]any
	if json.Unmarshal(schemaBytes, &root) != nil {
		return nil, invalid
	}
	defs := root["$defs"].(map[string]any)
	var expand func(any, int) (any, error)
	expand = func(v any, depth int) (any, error) {
		if depth > 32 {
			return nil, invalid
		}
		switch x := v.(type) {
		case map[string]any:
			if r, ok := x["$ref"].(string); ok {
				if len(x) != 1 || !strings.HasPrefix(r, "#/$defs/") {
					return nil, invalid
				}
				value, ok := defs[strings.TrimPrefix(r, "#/$defs/")]
				if !ok {
					return nil, invalid
				}
				return expand(value, depth+1)
			}
			out := map[string]any{}
			for k, c := range x {
				z, e := expand(c, depth+1)
				if e != nil {
					return nil, e
				}
				out[k] = z
			}
			return out, nil
		case []any:
			out := make([]any, len(x))
			for i, c := range x {
				z, e := expand(c, depth+1)
				if e != nil {
					return nil, e
				}
				out[i] = z
			}
			return out, nil
		default:
			return v, nil
		}
	}
	v, e := expand(map[string]any{"$ref": ref}, 0)
	if e != nil {
		return nil, e
	}
	return v.(map[string]any), nil
}
