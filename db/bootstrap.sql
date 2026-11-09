-- FUTURE dedicated, empty MCPBench container ONLY; bootstrap admin, once.
-- Passwords are provisioned separately through private deployment secrets.
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'mcpbench' THEN RAISE EXCEPTION 'dedicated mcpbench DB required'; END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'bench_control') THEN
   RAISE EXCEPTION 'already initialized; do not bootstrap existing state'; END IF;
END $$;
CREATE ROLE mcpbench_controller LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE mcpbench_service LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE mcpbench_grader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
-- This is a new dedicated MCPBench cluster: runtime roles connect only here.
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template0 FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
REVOKE ALL ON DATABASE mcpbench FROM PUBLIC;
GRANT CONNECT ON DATABASE mcpbench TO mcpbench_controller,mcpbench_service,mcpbench_grader;
ALTER DATABASE mcpbench OWNER TO mcpbench_controller;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER ROLE mcpbench_grader SET default_transaction_read_only = on;
SET LOCAL ROLE mcpbench_controller;
CREATE SCHEMA bench_control AUTHORIZATION mcpbench_controller;
REVOKE ALL ON SCHEMA bench_control FROM PUBLIC;
CREATE TABLE bench_control.run_registry (
 schema_version integer NOT NULL CHECK (schema_version = 1),
 run_id text PRIMARY KEY CHECK (run_id ~ '^[a-z][a-z0-9-]{0,63}$'),
 attempt_id text NOT NULL UNIQUE CHECK (attempt_id ~ '^[a-z][a-z0-9-]{0,63}$'),
 tenant_id text NOT NULL CHECK (tenant_id ~ '^[A-Z][A-Z0-9_-]{0,63}$'),
 principal_id text NOT NULL CHECK (principal_id IN ('billing-reader','billing-drafter')),
 allowed_tools text[] NOT NULL CHECK (cardinality(allowed_tools) BETWEEN 1 AND 10),
 schema_name text NOT NULL UNIQUE CHECK (schema_name ~ '^r_[0-9a-f]{32}$'),
 phase text NOT NULL CHECK (phase IN ('prepared','executing','agent_sealed','verifying','final_sealed','quarantined','cleaned')),
 generation integer NOT NULL CHECK (generation BETWEEN 0 AND 2), not_after timestamptz NOT NULL,
 agent_token_sha256 text CHECK (agent_token_sha256 ~ '^[0-9a-f]{64}$'),
 verifier_token_sha256 text CHECK (verifier_token_sha256 ~ '^[0-9a-f]{64}$'),
 verifier_scope jsonb, lock_marker bigint NOT NULL CHECK (lock_marker BETWEEN 0 AND 9007199254740991),
 workflow_kind text NOT NULL CHECK (workflow_kind IN ('draft_invoice','read_only'))
);
CREATE TABLE bench_control.schema_migrations (
 run_id text PRIMARY KEY REFERENCES bench_control.run_registry,
 version integer NOT NULL CHECK (version = 1),
 migration_sha256 text NOT NULL CHECK (migration_sha256 ~ '^[0-9a-f]{64}$'),
 fixture_version text NOT NULL CHECK (fixture_version = '1'),
 tenant_id text NOT NULL CHECK (tenant_id ~ '^[A-Z][A-Z0-9_-]{0,63}$'),
 seed_hash text NOT NULL CHECK (seed_hash ~ '^[0-9a-f]{64}$')
);
-- Defense against accidental controller routing changes after registration.
CREATE FUNCTION bench_control.immutable_identity() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog AS $$ BEGIN
 IF (NEW.run_id,NEW.attempt_id,NEW.tenant_id,NEW.principal_id,NEW.allowed_tools,NEW.schema_name,NEW.workflow_kind)
 IS DISTINCT FROM
 (OLD.run_id,OLD.attempt_id,OLD.tenant_id,OLD.principal_id,OLD.allowed_tools,OLD.schema_name,OLD.workflow_kind)
 THEN RAISE EXCEPTION 'immutable run binding'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_identity BEFORE UPDATE ON bench_control.run_registry
 FOR EACH ROW EXECUTE FUNCTION bench_control.immutable_identity();
REVOKE ALL ON ALL TABLES IN SCHEMA bench_control FROM PUBLIC;
REVOKE ALL ON FUNCTION bench_control.immutable_identity() FROM PUBLIC;
GRANT USAGE ON SCHEMA bench_control TO mcpbench_service,mcpbench_grader;
GRANT SELECT ON bench_control.run_registry TO mcpbench_service,mcpbench_grader;
GRANT UPDATE (lock_marker) ON bench_control.run_registry TO mcpbench_service;
COMMIT;
