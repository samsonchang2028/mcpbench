//go:build dependencies

// Retain the selected dependency during go mod tidy before runtime implementation.
// The dependencies build tag lets the scaffold compile-check the pinned library.
package store

import _ "github.com/jackc/pgx/v5"
