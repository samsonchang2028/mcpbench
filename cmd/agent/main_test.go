package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEntrypointFailsBeforeNetwork(t *testing.T) {
	for _, args := range [][]string{nil, {"run"}, {"other", "--request", "x", "--auth", "y", "--output", "z"}, {"run", "--auth", "x", "--request", "y", "--output", "z"}} {
		if execute(args) == nil {
			t.Fatal("accepted invalid fixed arguments")
		}
	}
	dir := t.TempDir()
	request := filepath.Join(dir, "request.json")
	auth := filepath.Join(dir, "auth.json")
	output := filepath.Join(dir, "output")
	if e := os.Mkdir(output, 0700); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(request, []byte(`{"schema_version":1,"schema_version":1}`), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(auth, []byte(`{}`), 0600); e != nil {
		t.Fatal(e)
	}
	if execute([]string{"run", "--request", request, "--auth", auth, "--output", output}) == nil {
		t.Fatal("accepted invalid documents")
	}
	entries, _ := os.ReadDir(output)
	if len(entries) != 0 {
		t.Fatal("invalid input published artifacts")
	}
}
