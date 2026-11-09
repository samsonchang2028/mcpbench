# T012 focused re-review

Candidate: `0fe5bc62ccf3e253847e17d2dea5e2b6ce71356a` in `.worktrees/T012`, repair compared with prior reviewed `77f3e893981b1c54284896b64585a928a12a0d57`.

Verdict: **APPROVE for source review**. The prior P1 is resolved; no new P0/P1 found in this bounded repair. The original review's remaining runtime evidence limits still apply.

The list branches now call `Session.ActiveCustomers` / `ActiveItems`. The concrete store applies `WHERE active` before `ORDER BY` and `LIMIT 101`, then rejects more than 100 returned active records instead of truncating. Inactive rows therefore neither appear in list output nor consume its cap. Creation retains the original unfiltered `Customers` / `Items` methods and its explicit `inactive_record` versus `not_found` validation behavior. Registry authorization, transaction/ACK handling, write and replay logic are unchanged.

Inspected the added tests for both tools: empty and inactive-only lists, mixed descending records, 150 inactive rows beside a valid active set, exactly 100 active rows, and 101 active rows returning `tool_error` with no committed result. The tests invoke the real service/store path with a fake query transport and separately require the expected SQL filter/order/bound. Additional checks preserve unfiltered creation reads and missing-versus-inactive outcomes without writes. Documentation accurately describes the distinction and labels database evidence UNRUN.

This reviewer performed static diff/caller inspection only, with no test execution, SQL, connections, containers or source changes. Root's independent tester owns cached-check results; actual PostgreSQL list execution, concurrency, privileges and lifecycle settlement remain a separate admitted T018 gate. This approval does not claim runtime PASS or mark T012/T018 complete.
