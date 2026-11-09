package mcp

import (
	"context"
	"errors"
	"os"
	"strings"
	"sync"

	"github.com/jackc/pgx/v5"
)

// Source limits fresh dedicated service connections to five. It is deliberately
// unpooled: transaction completion closes the connection and releases its slot.
// Acquisition, connect and transaction all share the caller's bounded context.
type Source struct {
	config *pgx.ConnConfig
	slots  chan struct{}
}

func ServiceSource() (*Source, error) {
	allowed := map[string]string{"PGHOST": "db", "PGPORT": "5432", "PGDATABASE": "mcpbench", "PGUSER": "mcpbench_service", "PGPASSFILE": "/run/secrets/service.pgpass"}
	for _, entry := range os.Environ() {
		key, value, _ := strings.Cut(entry, "=")
		if strings.HasPrefix(key, "PG") {
			expected, ok := allowed[key]
			if !ok || value != expected {
				return nil, invalid
			}
		}
	}
	config, err := pgx.ParseConfig("host=db port=5432 dbname=mcpbench user=mcpbench_service passfile=/run/secrets/service.pgpass sslmode=disable connect_timeout=5")
	if err != nil || config.Password == "" {
		return nil, invalid
	}
	config.RuntimeParams = map[string]string{"application_name": "mcpbench-service"}
	return &Source{config: config, slots: make(chan struct{}, 5)}, nil
}
func (s *Source) connect(ctx context.Context) (*pgx.Conn, func(), error) {
	if err := ctx.Err(); err != nil {
		return nil, nil, err
	}
	select {
	case s.slots <- struct{}{}:
	case <-ctx.Done():
		return nil, nil, ctx.Err()
	}
	release := func() { <-s.slots }
	c, err := pgx.ConnectConfig(ctx, s.config.Copy())
	if err != nil {
		release()
		return nil, nil, errors.New("service unavailable")
	}
	return c, func() { c.Close(ctx); release() }, nil
}
func (s *Source) BeginTx(ctx context.Context, o pgx.TxOptions) (pgx.Tx, error) {
	c, release, err := s.connect(ctx)
	if err != nil {
		return nil, err
	}
	tx, err := c.BeginTx(ctx, o)
	if err != nil {
		release()
		return nil, err
	}
	return &ownedTx{Tx: tx, release: release}, nil
}

type ownedTx struct {
	pgx.Tx
	once    sync.Once
	release func()
}

func (t *ownedTx) Commit(ctx context.Context) error {
	defer t.once.Do(t.release)
	return t.Tx.Commit(ctx)
}
func (t *ownedTx) Rollback(ctx context.Context) error {
	defer t.once.Do(t.release)
	return t.Tx.Rollback(ctx)
}

// Ready checks real dedicated identity and the frozen control-plane columns.
// It neither invents an active run nor claims that a per-run fixture is seeded.
func (s *Source) Ready(ctx context.Context) error {
	c, release, err := s.connect(ctx)
	if err != nil {
		return err
	}
	defer release()
	var role, login, db string
	if c.QueryRow(ctx, "SELECT current_user, session_user, current_database()").Scan(&role, &login, &db) != nil || role != "mcpbench_service" || login != "mcpbench_service" || db != "mcpbench" {
		return invalid
	}
	rows, err := c.Query(ctx, `SELECT run_id,attempt_id,tenant_id,principal_id,allowed_tools,schema_name,phase,generation,not_after,agent_token_sha256,verifier_token_sha256,verifier_scope,workflow_kind FROM bench_control.run_registry LIMIT 0`)
	if err != nil {
		return invalid
	}
	rows.Close()
	if rows.Err() != nil {
		return invalid
	}
	return nil
}
