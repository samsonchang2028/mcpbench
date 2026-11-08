"""Scoped reset backend contract. There is intentionally no SQL implementation."""
from copy import deepcopy
from typing import Protocol

from contracts.validate import validate
from eval.grading.oracle import (
    RunScope, bind_snapshot, evidence, fingerprint, identity, registration, require,
)


class ResetBackend(Protocol):
    """Trusted adapter, bounded to 5000 ms per operation by its implementation.

    read/reset must use only the dedicated MCPBench DB and registered
    schema. reset returns literal True only after positive COMMIT acknowledgment.
    Missing acknowledgment is failure, not permission to retry or reuse.
    """
    def read_mapping(self, scope: RunScope) -> dict: ...
    def reset_seed(self, scope: RunScope, schema: str, fixture: dict) -> bool: ...
    def snapshot(self, scope: RunScope, schema: str, stage: str) -> dict: ...


@evidence
def check_seed(fixture, snapshot, mapping, scope, stage):
    registration(mapping, scope, fixture)
    validate('Snapshot', snapshot)
    identity(snapshot, scope)
    require(mapping['phase'] in ({'prepared'} if stage == 'before' else
                                 {'prepared', 'agent_sealed', 'final_sealed'}), 'unsafe seed phase')
    require(stage in {'before', 'after_reset'} and snapshot['stage'] == stage,
            'wrong seed snapshot stage')
    require(snapshot['settlement_generation'] == mapping['generation'], 'stale seed snapshot')
    require(fingerprint(fixture, snapshot['tables']) == fixture['seed_hash'], 'seed fingerprint mismatch')


@evidence
def reset_and_check(backend: ResetBackend, scope, fixture, *, receipt=None,
                    evidence_persisted=False):
    """Initial prepare or settled cleanup. Failed evidence means quarantine/no reuse."""
    mapping = deepcopy(backend.read_mapping(scope))
    registration(mapping, scope, fixture)
    initial = mapping['phase'] == 'prepared' and mapping['generation'] == 0
    if not initial:
        require(evidence_persisted is True, 'evidence not persisted')
        # Use a trusted captured snapshot to bind receipt and current registration
        # before mutation. Diagnostic, active, quarantined and cleaned states fail.
        stage = 'agent_only' if mapping['phase'] == 'agent_sealed' else 'final'
        captured = backend.snapshot(scope, mapping['schema_name'], stage)
        bind_snapshot(captured, mapping, receipt, scope, stage)
    require(mapping['agent_token_sha256'] is None and mapping['verifier_token_sha256'] is None,
            'capability still active')
    # Copy private immutable seed so an adapter cannot change caller oracle data.
    require(backend.reset_seed(scope, mapping['schema_name'], deepcopy(fixture)) is True,
            'reset not acknowledged')
    current = backend.read_mapping(scope)
    require(current == mapping, 'registry changed during reset')
    snapshot = backend.snapshot(scope, mapping['schema_name'], 'after_reset')
    require(check_seed(fixture, snapshot, mapping, scope, 'after_reset').passed,
            'reset did not restore canonical seed')
