package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"testing"
	"time"
)

func parityTrace(t *testing.T, b []byte) {
	t.Helper()
	p := os.Getenv("MCPBENCH_TEST_PYTHON")
	if p == "" {
		t.Fatal("MCPBENCH_TEST_PYTHON required for real validator parity")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c := exec.CommandContext(ctx, p, "-c", `import sys
from contracts.validate import load_bytes,validate,validate_event_stream
es=[load_bytes(x) for x in sys.stdin.buffer if x.strip()]
for e in es: validate("Event",e)
validate_event_stream(es)
`)
	c.Dir = "../.."
	c.Stdin = bytes.NewReader(b)
	if out, e := c.CombinedOutput(); e != nil {
		t.Fatalf("real validator parity: %v %s", e, out)
	}
}

func parityObject(t *testing.T, kind string, v any) {
	t.Helper()
	b, _ := json.Marshal(v)
	p := os.Getenv("MCPBENCH_TEST_PYTHON")
	if p == "" {
		t.Fatal("MCPBENCH_TEST_PYTHON required")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c := exec.CommandContext(ctx, p, "-c", `import sys
from contracts.validate import load_bytes,validate,SCHEMA,REGISTRY
from jsonschema import Draft202012Validator
v=load_bytes(sys.stdin.buffer.read())
for err in Draft202012Validator({"$ref":"https://mcpbench.local/contracts/v1/schema.json#/$defs/"+sys.argv[1]},registry=REGISTRY).iter_errors(v): print(list(err.path),err.message)
validate(sys.argv[1],v)
`, kind)
	c.Dir = "../.."
	c.Stdin = bytes.NewReader(b)
	if out, e := c.CombinedOutput(); e != nil {
		t.Fatalf("real %s validation: %v %s", kind, e, out)
	}
}
