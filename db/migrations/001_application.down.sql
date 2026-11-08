-- Intentionally no CASCADE: unknown dependent objects prevent rollback.
DROP TABLE __SCHEMA__.idempotency_records;
DROP TABLE __SCHEMA__.invoice_lines;
DROP TABLE __SCHEMA__.invoices;
DROP FUNCTION __SCHEMA__.check_invoice();
DROP TABLE __SCHEMA__.timesheets;
DROP TABLE __SCHEMA__.projects;
DROP TABLE __SCHEMA__.items;
DROP TABLE __SCHEMA__.customers;
DROP DOMAIN __SCHEMA__.money;
DROP DOMAIN __SCHEMA__.business_id;
