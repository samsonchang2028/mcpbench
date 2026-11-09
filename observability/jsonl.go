// Package observability writes bounded, durable source-local JSONL files.
// It performs no network access, subprocess execution or background work.
package observability

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"
	"unicode/utf8"
)

// Validator must validate the complete final redacted Event, including frozen
// contract semantics and nested objects. A shape-only callback is insufficient.
// It must not mutate or retain its argument. There is no permissive default.
type Validator func(map[string]any) error

type Context struct{ RunID, AttemptID, Source string }
type Record struct {
	Type, Phase, Status  string
	Data                 map[string]any
	CallID, ParentCallID string
}
type Options struct {
	Validate                     Validator
	Secrets                      []string
	MaxBytes, MaxLine, MaxEvents int
	// Now must preserve monotonic time; production defaults to time.Now.
	Now func() time.Time
}
type Summary struct {
	Events, Bytes, OpenOperations int
	Closed, ArtifactComplete      bool
	Error                         string
}
type durableFile interface {
	io.Writer
	Sync() error
	Close() error
}
type operation struct {
	phase, parent string
	identity      map[string]any
}
type Writer struct {
	mu           sync.Mutex
	file         durableFile
	context      Context
	options      Options
	start        time.Time
	last         float64
	count, bytes int
	closed       bool
	failure      string
	opened       map[string]operation
	seen         map[string]bool
}

var identifier = regexp.MustCompile(`^[a-z][a-z0-9-]{0,63}$`)
var sensitive = regexp.MustCompile(`(?i)(password|passwd|secret|credential|authorization|capability|database_url|pgpass|(^|_)dsn$|(^|_)api[_-]?key$|(^|_)access[_-]token$|(^|_)refresh[_-]token$|^token$)`)
var content = regexp.MustCompile(`(?i)(\bbearer\s+\S+|\b(password|passwd|secret|token|api[_-]?key|authorization|capability|credential|dsn|database_url|access[_-]token|refresh[_-]token)\s*[=:]\s*\S+|[a-z][a-z0-9+.-]*://[^/\s]*@)`)

const Redacted = "[REDACTED]"

// LogError contains only a fixed category. Never wrap an underlying I/O or
// validation error, which might contain a path, credential or arbitrary value.
type LogError string

func (e LogError) Error() string { return string(e) }

// New creates a new 0600 file exclusively; it never resumes or appends to an
// existing trace. The launcher must supply a trusted, symlink-free parent tree.
func New(path string, context Context, options Options) (*Writer, error) {
	if !identifier.MatchString(context.RunID) || !identifier.MatchString(context.AttemptID) ||
		!contains([]string{"launcher", "evaluator", "agent", "mcp"}, context.Source) {
		return nil, LogError("context")
	}
	if options.Validate == nil {
		return nil, LogError("validator_required")
	}
	if options.MaxBytes == 0 {
		options.MaxBytes = 16 * 1024 * 1024
	}
	if options.MaxLine == 0 {
		options.MaxLine = 1024 * 1024
	}
	if options.MaxEvents == 0 {
		options.MaxEvents = 2500
	}
	if options.MaxBytes < 1 || options.MaxBytes > 100*1024*1024 || options.MaxLine < 1 || options.MaxLine > 1024*1024 || options.MaxEvents < 1 || options.MaxEvents > 10000 {
		return nil, LogError("limits")
	}
	options.Secrets = append([]string(nil), options.Secrets...)
	for _, secret := range options.Secrets {
		if secret == "" || !utf8.ValidString(secret) {
			return nil, LogError("secrets")
		}
	}
	if options.Now == nil {
		options.Now = time.Now
	}
	// Anchor creation to the verified immediate parent; ancestors are a launcher obligation.
	directoryFD, err := syscall.Open(filepath.Dir(path), syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, LogError("open")
	}
	directory := os.NewFile(uintptr(directoryFD), "event-directory")
	defer directory.Close()
	fd, err := syscall.Openat(directoryFD, filepath.Base(path), syscall.O_WRONLY|syscall.O_CREAT|syscall.O_EXCL|syscall.O_NOFOLLOW, 0600)
	if err != nil {
		return nil, LogError("open")
	}
	file := os.NewFile(uintptr(fd), "events")
	if err := directory.Sync(); err != nil {
		file.Close()
		return nil, LogError("open")
	}
	return &Writer{file: file, context: context, options: options, start: options.Now(), opened: map[string]operation{}, seen: map[string]bool{}}, nil
}
func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
func (w *Writer) fail(code string) error {
	if w.failure == "" {
		w.failure = code
	}
	return LogError(w.failure)
}
func (w *Writer) Summary() Summary {
	w.mu.Lock()
	defer w.mu.Unlock()
	return Summary{Events: w.count, Bytes: w.bytes, OpenOperations: len(w.opened), Closed: w.closed,
		ArtifactComplete: w.closed && w.failure == "" && w.count > 0 && len(w.opened) == 0, Error: w.failure}
}

// Redact copies strict JSON-compatible data without altering numeric token
// metrics. Known literal secrets and recognizable credential-bearing strings
// are removed. Unknown arbitrary error text must instead be a safe category.
func Redact(value any, secrets []string) (any, error) {
	for _, secret := range secrets {
		if secret == "" || !utf8.ValidString(secret) {
			return nil, LogError("secrets")
		}
	}
	ordered := append([]string(nil), secrets...)
	sort.SliceStable(ordered, func(i, j int) bool { return len(ordered[i]) > len(ordered[j]) })
	pairs := make([]string, 0, 2*len(ordered))
	for _, secret := range ordered {
		pairs = append(pairs, secret, Redacted)
	}
	replacer := strings.NewReplacer(pairs...)
	budget := 1024 * 1024
	return redact(value, secrets, 0, &budget, replacer)
}
func redact(value any, secrets []string, depth int, budget *int, replacer *strings.Replacer) (any, error) {
	*budget -= 1
	if depth > 32 || *budget < 0 {
		return nil, LogError("data_limit")
	}
	switch value := value.(type) {
	case map[string]any:
		result := make(map[string]any)
		for key, child := range value {
			if !utf8.ValidString(key) {
				return nil, LogError("data_unicode")
			}
			*budget -= len(key)
			if *budget < 0 {
				return nil, LogError("data_limit")
			}
			for _, secret := range secrets {
				if strings.Contains(key, secret) {
					return nil, LogError("data_key_secret")
				}
			}
			if sensitive.MatchString(key) {
				result[key] = Redacted
				continue
			}
			redacted, err := redact(child, secrets, depth+1, budget, replacer)
			if err != nil {
				return nil, err
			}
			result[key] = redacted
		}
		return result, nil
	case []any:
		result := make([]any, 0)
		for _, child := range value {
			redacted, err := redact(child, secrets, depth+1, budget, replacer)
			if err != nil {
				return nil, err
			}
			result = append(result, redacted)
		}
		return result, nil
	case string:
		*budget -= len(value)
		if *budget < 0 {
			return nil, LogError("data_limit")
		}
		if !utf8.ValidString(value) {
			return nil, LogError("data_unicode")
		}
		if content.MatchString(value) {
			return Redacted, nil
		}
		return replacer.Replace(value), nil
	case nil, bool, int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64:
		return value, nil
	case float64:
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return nil, LogError("data_number")
		}
		return value, nil
	case float32:
		if math.IsNaN(float64(value)) || math.IsInf(float64(value), 0) {
			return nil, LogError("data_number")
		}
		return value, nil
	default:
		return nil, LogError("data_type")
	}
}

func (w *Writer) Emit(record Record) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.closed {
		return w.fail("closed")
	}
	if w.failure != "" {
		return LogError(w.failure)
	}
	now := w.options.Now()
	elapsed := now.Sub(w.start).Seconds() * 1000
	if elapsed < w.last || elapsed < 0 || elapsed > 86400000 {
		return w.fail("clock")
	}
	data, err := Redact(record.Data, w.options.Secrets)
	if err != nil {
		return w.fail("data")
	}
	event := map[string]any{"schema_version": 1, "run_id": w.context.RunID, "attempt_id": w.context.AttemptID,
		"source": w.context.Source, "event_id": fmt.Sprintf("%s-%d", w.context.Source, w.count+1),
		"sequence": w.count + 1, "timestamp": now.UTC().Format("2006-01-02T15:04:05.000000Z"),
		"event_type": record.Type, "phase": record.Phase, "status": record.Status, "elapsed_ms": elapsed, "data": data}
	if record.CallID != "" {
		event["call_id"] = record.CallID
	}
	if record.ParentCallID != "" {
		event["parent_call_id"] = record.ParentCallID
	}
	for key, value := range event {
		if key == "data" {
			continue
		}
		text, _ := json.Marshal(value)
		for _, secret := range w.options.Secrets {
			if strings.Contains(string(text), secret) {
				return w.fail("metadata_secret")
			}
		}
	}
	// Only final redacted data reaches the semantic gate.
	if err := w.options.Validate(event); err != nil {
		return w.fail("event")
	}
	kind, suffix, _ := strings.Cut(record.Type, ".")
	key := kind + "\x00" + record.CallID
	paired := contains([]string{"model", "tool", "db"}, kind)
	fields := []string{}
	if kind == "tool" {
		fields = []string{"tool_id"}
	} else if kind == "db" {
		fields = []string{"operation", "transaction_id"}
	} else if kind == "model" && suffix == "completed" {
		fields = []string{"model_digest", "prompt_hash"}
	}
	object := data.(map[string]any)
	if paired {
		if suffix == "started" {
			if w.seen[key] {
				return w.fail("call_reused")
			}
		} else {
			start, ok := w.opened[key]
			if !ok || start.phase != record.Phase || start.parent != record.ParentCallID {
				return w.fail("correlation")
			}
			for _, field := range fields {
				if start.identity[field] != object[field] {
					return w.fail("call_identity")
				}
			}
		}
	}
	raw, err := json.Marshal(event)
	if err != nil {
		return w.fail("encoding")
	}
	raw = append(raw, '\n')
	if len(raw) > w.options.MaxLine || w.bytes+len(raw) > w.options.MaxBytes || w.count >= w.options.MaxEvents {
		return w.fail("capacity")
	}
	n, err := w.file.Write(raw)
	if err != nil {
		return w.fail("write")
	}
	if n != len(raw) {
		return w.fail("short_write")
	}
	if err := w.file.Sync(); err != nil {
		return w.fail("sync")
	}
	w.count++
	w.bytes += len(raw)
	w.last = elapsed
	if paired {
		if suffix == "started" {
			w.seen[key] = true
			w.opened[key] = operation{phase: record.Phase, parent: record.ParentCallID, identity: object}
		} else {
			delete(w.opened, key)
		}
	}
	return nil
}

// Close always attempts to sync and close. Any earlier failure, empty file or
// unfinished local operation leaves ArtifactComplete false, with a stable error.
func (w *Writer) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.closed {
		if w.failure != "" {
			return LogError(w.failure)
		}
		return nil
	}
	if err := w.file.Sync(); err != nil {
		w.fail("sync")
	}
	if err := w.file.Close(); err != nil {
		w.fail("close")
	}
	w.closed = true
	if w.count == 0 {
		w.fail("empty")
	}
	if len(w.opened) > 0 {
		w.fail("unclosed_operation")
	}
	if w.failure != "" {
		return LogError(w.failure)
	}
	return nil
}

// AddSecrets installs newly minted private literals before their requests are
// admitted. It retains its own copy and never resets sequence or elapsed time.
// Invalid updates are atomic: none of their literals are installed.
func (w *Writer) AddSecrets(secrets []string) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.closed {
		return LogError("closed")
	}
	if w.failure != "" {
		return LogError(w.failure)
	}
	for _, secret := range secrets {
		if secret == "" || !utf8.ValidString(secret) {
			return LogError("secrets")
		}
	}
	w.options.Secrets = append(w.options.Secrets, secrets...)
	return nil
}
