package ollama

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"math"
	"strconv"
	"strings"
	"unicode/utf8"
)

var invalid = errors.New("invalid JSON document")

func StrictJSON(b []byte) (any, error) { return strictJSON(b, false) }

// Model wire arguments remain raw so the agent can record rejected decimal or
// exponent quantities and duplicate keys as attempted selections without dispatch.
// Only the scanner ignores argument duplicates; json.RawMessage retains the exact
// bytes for strict rejection in ValidateArguments before any tool dispatch.
func strictJSON(b []byte, modelWire bool) (any, error) {
	if len(b) > 1048576 || !utf8.Valid(b) {
		return nil, invalid
	}
	// encoding/json replaces lone surrogates; reject them before decoding.
	for i := 0; i < len(b); i++ {
		if b[i] == '\\' {
			i++
			if i < len(b) && b[i] == 'u' && i+4 < len(b) {
				n, e := strconv.ParseUint(string(b[i+1:i+5]), 16, 16)
				if e != nil {
					return nil, invalid
				}
				i += 4
				if n >= 0xd800 && n <= 0xdbff {
					if i+6 >= len(b) || string(b[i+1:i+3]) != "\\u" {
						return nil, invalid
					}
					m, e := strconv.ParseUint(string(b[i+3:i+7]), 16, 16)
					if e != nil || m < 0xdc00 || m > 0xdfff {
						return nil, invalid
					}
					i += 6
				} else if n >= 0xdc00 && n <= 0xdfff {
					return nil, invalid
				}
			}
		}
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	var walk func(int, string, bool) (any, error)
	walk = func(depth int, key string, arguments bool) (any, error) {
		if depth > 64 {
			return nil, invalid
		}
		t, e := d.Token()
		if e != nil {
			return nil, invalid
		}
		switch x := t.(type) {
		case json.Delim:
			if x == '{' {
				m := map[string]any{}
				for d.More() {
					k, e := d.Token()
					if e != nil {
						return nil, invalid
					}
					s, ok := k.(string)
					if !ok {
						return nil, invalid
					}
					if _, ok = m[s]; ok && !(modelWire && arguments) {
						return nil, invalid
					}
					v, e := walk(depth+1, s, arguments || modelWire && s == "arguments")
					if e != nil {
						return nil, e
					}
					m[s] = v
				}
				_, e = d.Token()
				return m, e
			}
			if x == '[' {
				a := []any{}
				for d.More() {
					v, e := walk(depth+1, key, arguments)
					if e != nil {
						return nil, e
					}
					a = append(a, v)
				}
				_, e = d.Token()
				return a, e
			}
			return nil, invalid
		case json.Number:
			if !modelWire && key != "elapsed_ms" && key != "remaining_ms" && key != "operation_timeout_ms" && key != "duration_ms" && strings.ContainsAny(string(x), ".eE") {
				return nil, invalid
			}
			n, e := strconv.ParseFloat(string(x), 64)
			if e != nil || math.IsInf(n, 0) || math.Abs(n) > 9007199254740991 {
				return nil, invalid
			}
			return n, nil
		default:
			return t, nil
		}
	}
	v, e := walk(0, "", false)
	if e != nil {
		return nil, e
	}
	if _, e = d.Token(); e != io.EOF {
		return nil, invalid
	}
	return v, nil
}
