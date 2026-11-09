package agent

import (
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"syscall"
)

// ReadDocument rejects links in the full path and bounds all input bytes. The
// launcher still owns mount isolation and ownership checks.
func ReadDocument(path string) ([]byte, error) {
	if e := safePath(path); e != nil {
		return nil, e
	}
	fd, e := syscall.Open(path, syscall.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if e != nil {
		return nil, invalid
	}
	f := os.NewFile(uintptr(fd), "input")
	defer f.Close()
	st, e := f.Stat()
	if e != nil || !st.Mode().IsRegular() || st.Size() > 1048576 {
		return nil, invalid
	}
	b, e := io.ReadAll(io.LimitReader(f, 1048577))
	if e != nil || len(b) > 1048576 {
		return nil, invalid
	}
	return b, nil
}
func safePath(path string) error {
	p, e := filepath.Abs(path)
	if e != nil {
		return invalid
	}
	for {
		st, e := os.Lstat(p)
		if e != nil || st.Mode()&os.ModeSymlink != 0 {
			return invalid
		}
		next := filepath.Dir(p)
		if next == p {
			break
		}
		p = next
	}
	return nil
}

// WriteResult uses a same-directory fsynced temporary file and an atomic hard
// link publication, which unlike os.Rename cannot replace an existing result.
func WriteResult(dir string, v any) error {
	if safePath(dir) != nil {
		return invalid
	}
	b, e := json.Marshal(v)
	if e != nil || len(b) > 1048576 {
		return invalid
	}
	fd, e := syscall.Open(dir, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW, 0)
	if e != nil {
		return invalid
	}
	d := os.NewFile(uintptr(fd), "output")
	defer d.Close()
	f, e := os.CreateTemp(dir, ".result-*")
	if e != nil {
		return invalid
	}
	name := f.Name()
	defer os.Remove(name)
	if e = f.Chmod(0600); e == nil {
		_, e = f.Write(b)
	}
	if e == nil {
		e = f.Sync()
	}
	ce := f.Close()
	if e != nil || ce != nil {
		return invalid
	}
	if e = os.Link(name, filepath.Join(dir, "result.json")); e != nil {
		return invalid
	}
	if d.Sync() != nil {
		return invalid
	}
	return nil
}
func CheckOutput(dir string) error {
	if safePath(dir) != nil {
		return invalid
	}
	s, e := os.Stat(dir)
	if e != nil || !s.IsDir() {
		return invalid
	}
	for _, name := range []string{"result.json", "events.jsonl"} {
		if _, e := os.Lstat(filepath.Join(dir, name)); !os.IsNotExist(e) {
			return invalid
		}
	}
	return nil
}
