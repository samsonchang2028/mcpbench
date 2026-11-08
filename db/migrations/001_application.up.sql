-- __SCHEMA__ is replaced only with psycopg.sql.Identifier of a registered schema.
CREATE DOMAIN __SCHEMA__.business_id AS text CHECK (VALUE ~ '^[A-Z][A-Z0-9_-]{0,63}$');
CREATE DOMAIN __SCHEMA__.money AS bigint CHECK (VALUE BETWEEN 0 AND 9007199254740991);
CREATE TABLE __SCHEMA__.customers (
 customer_id __SCHEMA__.business_id PRIMARY KEY,
 name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200), active boolean NOT NULL
);
CREATE TABLE __SCHEMA__.items (
 item_id __SCHEMA__.business_id PRIMARY KEY,
 name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
 unit text NOT NULL CHECK (unit IN ('hour','unit')),
 currency text NOT NULL CHECK (currency = 'USD'),
 unit_price_cents __SCHEMA__.money NOT NULL, active boolean NOT NULL
);
CREATE TABLE __SCHEMA__.projects (
 project_id __SCHEMA__.business_id PRIMARY KEY,
 customer_id __SCHEMA__.business_id NOT NULL REFERENCES __SCHEMA__.customers,
 name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200), active boolean NOT NULL
);
CREATE TABLE __SCHEMA__.timesheets (
 timesheet_id __SCHEMA__.business_id PRIMARY KEY,
 project_id __SCHEMA__.business_id NOT NULL REFERENCES __SCHEMA__.projects,
 item_id __SCHEMA__.business_id NOT NULL REFERENCES __SCHEMA__.items,
 work_date date NOT NULL CHECK (work_date BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'),
 minutes integer NOT NULL CHECK (minutes BETWEEN 1 AND 1440), billable boolean NOT NULL
);
CREATE TABLE __SCHEMA__.invoices (
 invoice_id __SCHEMA__.business_id PRIMARY KEY,
 customer_id __SCHEMA__.business_id NOT NULL REFERENCES __SCHEMA__.customers,
 invoice_date date NOT NULL CHECK (invoice_date BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'),
 due_date date NOT NULL CHECK (due_date BETWEEN invoice_date AND DATE '9999-12-31'),
 currency text NOT NULL CHECK (currency = 'USD'), status text NOT NULL CHECK (status = 'draft'),
 subtotal_cents __SCHEMA__.money NOT NULL, tax_cents bigint NOT NULL CHECK (tax_cents = 0),
 total_cents __SCHEMA__.money NOT NULL CHECK (total_cents = subtotal_cents),
 created_at timestamptz NOT NULL CHECK (created_at >= TIMESTAMPTZ '0001-01-01 00:00:00+00' AND created_at < TIMESTAMPTZ '10000-01-01 00:00:00+00')
);
CREATE TABLE __SCHEMA__.invoice_lines (
 line_id __SCHEMA__.business_id PRIMARY KEY,
 invoice_id __SCHEMA__.business_id NOT NULL REFERENCES __SCHEMA__.invoices,
 item_id __SCHEMA__.business_id NOT NULL REFERENCES __SCHEMA__.items,
 quantity integer NOT NULL CHECK (quantity BETWEEN 1 AND 1000),
 unit_price_cents __SCHEMA__.money NOT NULL,
 line_total_cents __SCHEMA__.money NOT NULL CHECK (line_total_cents::numeric = quantity::numeric * unit_price_cents::numeric),
 line_number integer NOT NULL CHECK (line_number BETWEEN 1 AND 10),
 UNIQUE (invoice_id,line_number), UNIQUE (invoice_id,item_id)
);
CREATE TABLE __SCHEMA__.idempotency_records (
 idempotency_key text PRIMARY KEY CHECK (idempotency_key ~ '^[a-z][a-z0-9-]{0,63}$'),
 request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
 invoice_id __SCHEMA__.business_id NOT NULL UNIQUE REFERENCES __SCHEMA__.invoices
);
-- Deferred checks allow header, ordered lines and ledger to be inserted atomically.
-- Invoker rights suffice: service has SELECT, INSERT, schema USAGE, function EXECUTE.
CREATE FUNCTION __SCHEMA__.check_invoice() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog AS $$
DECLARE target text; n bigint; last_line integer; total numeric; header_total bigint;
BEGIN
 target := NEW.invoice_id;
 SELECT count(*), max(line_number), sum(line_total_cents::numeric)
 INTO n, last_line, total FROM __SCHEMA__.invoice_lines WHERE invoice_id = target;
 SELECT subtotal_cents INTO header_total FROM __SCHEMA__.invoices WHERE invoice_id = target;
 IF n < 1 OR n > 10 OR last_line <> n OR total <> header_total OR
    (SELECT count(*) FROM __SCHEMA__.idempotency_records WHERE invoice_id = target) <> 1 THEN
   RAISE EXCEPTION 'inconsistent invoice' USING ERRCODE = '23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER invoice_complete AFTER INSERT ON __SCHEMA__.invoices
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION __SCHEMA__.check_invoice();
CREATE CONSTRAINT TRIGGER lines_complete AFTER INSERT ON __SCHEMA__.invoice_lines
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION __SCHEMA__.check_invoice();
CREATE CONSTRAINT TRIGGER ledger_complete AFTER INSERT ON __SCHEMA__.idempotency_records
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION __SCHEMA__.check_invoice();
REVOKE ALL ON FUNCTION __SCHEMA__.check_invoice() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION __SCHEMA__.check_invoice() TO mcpbench_service;
GRANT USAGE ON SCHEMA __SCHEMA__ TO mcpbench_service, mcpbench_grader;
GRANT SELECT ON ALL TABLES IN SCHEMA __SCHEMA__ TO mcpbench_service, mcpbench_grader;
GRANT INSERT ON __SCHEMA__.invoices, __SCHEMA__.invoice_lines, __SCHEMA__.idempotency_records TO mcpbench_service;
