package mcp

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"syscall"

	"mcpbench/internal/agent"
	"mcpbench/internal/billing"
	"mcpbench/observability"
)

// TraceFiles is one trusted run's service trace. Config is a narrow read-only
// mount and output a different writable mount. Phase changes are launcher-owned;
// one writer retains MCP sequence/elapsed continuity through verification.
type TraceFiles struct {
	Config, Output      string
	mu                  sync.Mutex
	writer              *observability.Writer
	run, attempt, phase string
	secrets             []string
}
type TraceConfig struct {
	Version int      `json:"schema_version"`
	Run     string   `json:"run_id"`
	Attempt string   `json:"attempt_id"`
	Phase   string   `json:"phase"`
	Secrets []string `json:"secrets"`
}

func (t *TraceFiles) Events(run, attempt string) (*observability.Writer, string, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	info, err := os.Lstat(t.Config)
	if err != nil || info.Mode().Perm() != 0600 || !info.Mode().IsRegular() || info.Sys().(*syscall.Stat_t).Uid != uint32(os.Getuid()) {
		return nil, "", invalid
	}
	raw, err := agent.ReadDocument(t.Config)
	if err != nil {
		return nil, "", invalid
	}
	if _, err := agent.StrictJSON(raw); err != nil {
		return nil, "", invalid
	}
	var fields map[string]json.RawMessage
	var c TraceConfig
	if json.Unmarshal(raw, &fields) != nil || len(fields) != 5 || json.Unmarshal(raw, &c) != nil || c.Version != 1 || c.Run != run || c.Attempt != attempt || !billing.Identifier.MatchString(run) || !billing.Identifier.MatchString(attempt) || (c.Phase != "execution" && c.Phase != "verification") || len(c.Secrets) < 1 || len(c.Secrets) > 2 {
		return nil, "", invalid
	}
	for _, key := range []string{"schema_version", "run_id", "attempt_id", "phase", "secrets"} {
		if fields[key] == nil {
			return nil, "", invalid
		}
	}
	for _, s := range c.Secrets {
		if !capability.MatchString(s) {
			return nil, "", invalid
		}
	}
	if len(t.secrets) > len(c.Secrets) {
		return nil, "", invalid
	}
	for i, secret := range t.secrets {
		if c.Secrets[i] != secret {
			return nil, "", invalid
		}
	}
	t.secrets = append([]string(nil), c.Secrets...)
	if t.writer == nil {
		if c.Phase != "execution" {
			return nil, "", invalid
		}
		t.writer, err = observability.New(filepath.Join(t.Output, "events.jsonl"), observability.Context{RunID: run, AttemptID: attempt, Source: "mcp"}, observability.Options{Validate: ValidateEvent, Secrets: c.Secrets})
		if err != nil {
			return nil, "", err
		}
		t.run, t.attempt = run, attempt
	} else if t.run != run || t.attempt != attempt || (t.phase == "verification" && c.Phase != "verification") {
		return nil, "", invalid
	}
	if err := t.writer.AddSecrets(c.Secrets); err != nil {
		return nil, "", err
	}
	t.phase = c.Phase
	return t.writer, c.Phase, nil
}
func (t *TraceFiles) Close() error {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.writer != nil {
		return t.writer.Close()
	}
	return nil
}
