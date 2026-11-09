"""Offline typed launcher proofs. Scripted backend/children never prove live SQL."""
from copy import deepcopy
from datetime import timedelta
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from contracts.validate import canonical_bytes, load_bytes, validate
from eval.runner import Artifacts, Evaluator, Budget
from eval.runner.test_lifecycle import ScriptedBackend, NOW, example
from eval.runner import test_lifecycle as fixtures
from launcher.run import Launcher
from launcher.transport import DockerTransport, Outcome


class DockerLoggingTests(unittest.TestCase):
    def setUp(self):
        self.driver=DockerTransport({'agent':'sha256:'+'a'*64,'evaluator':'sha256:'+'b'*64,
                                     'mcp':'sha256:'+'c'*64,'gateway':'sha256:'+'d'*64},'/nonexistent/service.pgpass')
        root=Path('/nonexistent/mcpbench-test')
        self.paths={name:root/name for name in ('control','evaluator','mcp-control','mcp-output',
                    'agent-input','agent-output','verifier-input','verifier-output')}

    def assert_bounded_local_logs(self, command):
        self.assertEqual(command[command.index('--log-driver')+1],'local')
        self.assertEqual([command[i+1] for i,arg in enumerate(command) if arg=='--log-opt'],
                         ['max-size=1m','max-file=1','compress=false'])

    def test_child_phase_commands_disable_compression_with_one_log_file(self):
        for child,phase in [('agent','run'),('verifier','verify'),('evaluator','prepare'),
                            ('evaluator','settle-grade'),('evaluator','finalize')]:
            with self.subTest(child=child,phase=phase):
                self.assert_bounded_local_logs(self.driver.command(child,phase,self.paths))

    def test_mcp_start_command_disables_compression_with_one_log_file(self):
        # Stop at the subprocess boundary: no Docker, files or health calls occur.
        with patch('launcher.transport.subprocess.run',side_effect=RuntimeError('captured_command')) as run:
            with self.assertRaisesRegex(RuntimeError,'captured_command'):
                self.driver.start_mcp(self.paths,time.monotonic()+1,lambda:None)
        run.assert_called_once()
        self.assert_bounded_local_logs(run.call_args.args[0])


class Clock:
    now = 0
    def mono(self): return self.now
    def wall(self): return NOW+timedelta(seconds=self.now)


class ScriptedTransport:
    def __init__(self, clock, backend):
        self.clock,self.backend=clock,backend
        self.calls=[]
        self.fail=None
        self.unreaped=False
        self.bad_trace=None

    def execute(self, child, phase, paths, timeout, quota):
        self.calls.append((child,phase,timeout))
        if self.fail == phase:
            return Outcome(1,True,'exited',None,self.clock.now)
        files=Artifacts(paths['evaluator'])
        if child=='evaluator':
            request=load_bytes((paths['control']/'request.json').read_bytes())
            value=Evaluator(files,self.backend,monotonic=self.clock.mono,wall_clock=self.clock.wall).invoke(request)
            code=int(value['action'] in {'blocked','quarantine'})
        else:
            output=Artifacts(paths[child+'-output'])
            request=load_bytes((paths[child+'-input']/'transport/request.json').read_bytes())
            if child=='agent':
                self.backend.tables=deepcopy(self.backend.saved['tables'])
                result=example('agent-result')
                result.update(run_id=request['run_id'],attempt_id=request['attempt_id'])
                event=dict(schema_version=1,run_id=request['run_id'],attempt_id=request['attempt_id'],source='agent',
                           timestamp=self.clock.wall().isoformat().replace('+00:00','Z'),event_id='agent-1',sequence=1,
                           event_type='agent.finished',phase='agent',status='ok',elapsed_ms=1,data={'result':result})
                output.write_bytes('transport/events.jsonl',canonical_bytes(event)+b'\n')
                events=fixtures.LifecycleTests.invoice_trace(None,self.backend)
                Artifacts(paths['mcp-output']).write_bytes('trace/events.jsonl',b''.join(canonical_bytes(e)+b'\n' for e in events))
            else:
                result=example('verifier-result')
                for key in ('run_id','attempt_id','task_id','task_hash','config_hash','budget','invoice_id','idempotency_key','original_request_hash'):
                    result[key]=request[key]
                result['budget']=Budget(request['budget'],monotonic=self.clock.mono,wall_clock=self.clock.wall).observation()
                # Verifier's independent agent producer starts at sequence1.
                event=dict(schema_version=1,run_id=request['run_id'],attempt_id=request['attempt_id'],source='agent',
                    timestamp=self.clock.wall().isoformat().replace('+00:00','Z'),event_id='agent-1',sequence=1,
                    event_type='tool.started',phase='verification',status='ok',elapsed_ms=1,call_id='verify-test',
                    data={'tool_id':'billing_create_draft_invoice','arguments':request['original_arguments'],'retry_index':0})
                terminal={**event,'event_id':'agent-2','sequence':2,'event_type':'tool.completed','data':{
                    'tool_id':'billing_create_draft_invoice','duration_ms':1,'tool_result':result['checks'][0]['tool_result']}}
                output.write_bytes('transport/events.jsonl',canonical_bytes(event)+b'\n'+canonical_bytes(terminal)+b'\n')
            output.write('transport/result.json',result,contract='AgentResult' if child=='agent' else 'VerifierResult')
            if self.bad_trace==child:(output.root/'transport/events.jsonl').write_bytes(b'{}\n')
            code=0
        self.clock.now+=.001
        return Outcome(code,not self.unreaped,'exited' if not self.unreaped else 'timed_out',None,self.clock.now)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        os.chmod(self.tmp.name,0o700)
        self.clock=Clock();self.backend=ScriptedBackend()
        self.transport=ScriptedTransport(self.clock,self.backend)
        self.config=dict(mapping=deepcopy(self.backend.mapping),idempotency_key=self.backend.scope.idempotency_key,
                         model=example('agent-request')['model'],trace_paths=['events/agent.jsonl','events/mcp.jsonl'])
        self.control={'database.json':b'{}','controller.pgpass':b'synthetic-controller','grader.pgpass':b'synthetic-grader'}
        self.launcher=Launcher(self.tmp.name,self.transport,monotonic=self.clock.mono,wall=self.clock.wall)

    def run_attempt(self):
        return self.launcher.run(self.backend.task,self.backend.fixture,self.config,self.control)

    def test_typed_complete_and_restart_barrier(self):
        result=self.run_attempt()
        self.assertEqual(result['action'],'complete')
        self.assertTrue(result['original_pass'])
        files=Artifacts(self.launcher.paths['evaluator'])
        evaluation=files.read(result['outputs']['evaluation'],'EvaluationResult')
        self.assertTrue(evaluation['comparison_valid'])
        self.assertEqual(self.backend.tables,self.backend.seed)
        journal=Artifacts(self.launcher.root)
        chain=journal.load('journal/control-chain.json','ControlChain')
        self.assertEqual(len(chain['exits']),5)
        self.assertEqual((self.launcher.paths['control']/'result.json').read_bytes(),
                         (files.root/'control/finalize-result.json').read_bytes())
        self.assertEqual([x[:2] for x in self.transport.calls],[('evaluator','prepare'),('agent','run'),('evaluator','settle-grade'),('verifier','verify'),('evaluator','finalize')])
        self.assertTrue(all(timeout<=5 for child,phase,timeout in self.transport.calls if phase not in {'prepare','run'}))
        with self.assertRaises(FileExistsError):self.run_attempt()
        self.assertEqual(len(self.transport.calls),5)

    def test_evaluator_failure_outcomes_retain_exit_without_progression(self):
        scenarios = ('quarantine', 'missing', 'malformed', 'identity', 'budget',
                     'signaled', 'timed_out', 'unreaped', 'spawn_failed', 'expired', 'overdue', 'quota')
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                fixture = LauncherTests()
                fixture.setUp()
                try:
                    if scenario == 'quarantine':
                        fixture.backend.unknown = 'agent'
                    execute = fixture.transport.execute
                    def outcome(child, phase, paths, timeout, quota):
                        observed = execute(child, phase, paths, timeout, quota)
                        if child != 'evaluator' or phase != 'settle-grade':
                            return observed
                        target = paths['evaluator']/'control/settle-grade-result.json'
                        if scenario == 'missing':
                            target.unlink()
                        elif scenario == 'malformed':
                            target.write_bytes(b'{}\n')
                        elif scenario in {'identity', 'budget'}:
                            result = load_bytes(target.read_bytes())
                            if scenario == 'identity':
                                result['request_id'] = 'wrong-request'
                            else:
                                result['budget']['anchor_id'] = 'wrong-anchor'
                            target.write_bytes(canonical_bytes(result)+b'\n')
                        elif scenario == 'signaled':
                            return Outcome(None, True, 'terminated', 'SIGKILL', observed.ended_monotonic)
                        elif scenario == 'timed_out':
                            return Outcome(None, True, 'timed_out', 'SIGKILL', observed.ended_monotonic)
                        elif scenario == 'unreaped':
                            return Outcome(None, False, 'timed_out', None, observed.ended_monotonic)
                        elif scenario == 'spawn_failed':
                            return Outcome(None, False, 'spawn_failed', None, observed.ended_monotonic)
                        elif scenario == 'expired':
                            fixture.clock.now += 31
                        elif scenario == 'overdue':
                            fixture.clock.now += 6
                            return Outcome(0, True, 'exited', None, fixture.clock.now)
                        elif scenario == 'quota':
                            fixture.launcher.quota = lambda: (_ for _ in ()).throw(ValueError('artifact_limit'))
                        return Outcome(1 if scenario in {'missing','malformed','quarantine'} else 0,
                                       True, 'exited', None, observed.ended_monotonic)
                    fixture.transport.execute = outcome
                    with self.assertRaisesRegex(ValueError, 'quarantined'):
                        fixture.run_attempt()
                    root = fixture.launcher.root
                    record = Artifacts(root).load('journal/settle-grade-exit.json', 'ProcessExit')
                    if scenario in {'missing','malformed','quarantine'}:
                        self.assertEqual(record['exit_code'], 1)
                    if scenario in {'unreaped','spawn_failed'}:
                        self.assertFalse(record['reaped'])
                    if scenario in {'signaled','timed_out'}:
                        self.assertEqual(record['signal'], 'SIGKILL')
                    delivery = 'missing' if scenario in {'missing','spawn_failed'} else 'malformed' if scenario in {'malformed','identity','budget'} else 'complete'
                    self.assertEqual(record['result_delivery'], delivery)
                    if delivery == 'complete':
                        self.assertEqual((root/'journal/settle-grade-result.json').read_bytes(),
                                         (root/'evaluator/control/settle-grade-result.json').read_bytes())
                    self.assertEqual(fixture.backend.calls.count('reset'), 1)
                    self.assertNotIn('cleaned', fixture.backend.calls)
                    self.assertNotIn(('verifier','verify'), [call[:2] for call in fixture.transport.calls])
                    self.assertFalse((root/'journal/control-chain.json').exists())
                finally:
                    fixture.doCleanups()

    def test_blocked_prepare_exit_one_retains_typed_result(self):
        self.backend.reset_ok = False
        with self.assertRaisesRegex(ValueError, 'quarantined'):
            self.run_attempt()
        record = Artifacts(self.launcher.root).load('journal/prepare-exit.json', 'ProcessExit')
        self.assertEqual(record['exit_code'], 1)
        self.assertEqual(record['result_delivery'], 'complete')
        result = Artifacts(self.launcher.root).load('journal/prepare-result.json', 'ControlResult')
        self.assertEqual(result['action'], 'blocked')
        self.assertEqual(len(self.transport.calls), 1)

    def test_transport_failure_quarantines_without_reset_or_retry(self):
        self.transport.fail='settle-grade'
        with self.assertRaisesRegex(ValueError,'quarantined'):self.run_attempt()
        self.assertTrue((self.launcher.root/'journal/quarantine.json').exists())
        self.assertEqual(self.backend.calls.count('reset'),1)  # initial prepare reset only
        self.assertNotIn('cleaned',self.backend.calls)
        with self.assertRaises(FileExistsError):self.run_attempt()

    def test_unknown_fence_never_cleanup(self):
        self.backend.unknown='agent'
        with self.assertRaisesRegex(ValueError,'quarantined'):self.run_attempt()
        self.assertNotIn('cleaned',self.backend.calls)
        self.assertEqual(self.backend.calls.count('reset'),1)

    def test_missing_original_evidence_still_fences_before_quarantine(self):
        self.transport.bad_trace='agent'
        with self.assertRaisesRegex(ValueError,'quarantined'):self.run_attempt()
        self.assertIn('seal-agent',self.backend.calls)
        self.assertNotIn('cleaned',self.backend.calls)
        self.assertNotIn(('verifier','verify'),[x[:2] for x in self.transport.calls])
        self.assertEqual(self.backend.calls.count('reset'),1)

    def test_invalid_verifier_evidence_blocks_finalize_and_reset(self):
        self.transport.bad_trace='verifier'
        with self.assertRaisesRegex(ValueError,'quarantined'):self.run_attempt()
        self.assertIn('seal-agent',self.backend.calls)
        self.assertNotIn(('evaluator','finalize'),[x[:2] for x in self.transport.calls])
        self.assertNotIn('cleaned',self.backend.calls)
        self.assertEqual(self.backend.calls.count('reset'),1)

    def test_parent_symlink_rejected_before_child(self):
        alias=Path(self.tmp.name)/'alias';alias.symlink_to(self.tmp.name,target_is_directory=True)
        bad=Launcher(alias,self.transport)
        with self.assertRaises(Exception):bad.run(self.backend.task,self.backend.fixture,self.config,self.control)
        self.assertEqual(self.transport.calls,[])

    def test_aggregate_quota(self):
        self.run_attempt()
        with open(self.launcher.root/'overflow','wb') as out:out.truncate(100*1024**2)
        with self.assertRaisesRegex(ValueError,'artifact_limit'):self.launcher.quota()

    def test_fixed_command_and_mounts(self):
        self.run_attempt()
        driver=DockerTransport({'agent':'sha256:'+'a'*64,'evaluator':'sha256:'+'b'*64,'mcp':'sha256:'+'c'*64,'gateway':'sha256:'+'d'*64},'/nonexistent/service.pgpass')
        command=driver.command('agent','run',self.launcher.paths)
        joined=' '.join(command)
        self.assertNotIn('shell',joined)
        self.assertIn('--network host',joined)
        self.assertEqual(command.count('--mount'),3)
        self.assertNotIn(str(self.launcher.paths['evaluator']),joined)
        self.assertNotIn(str(self.launcher.paths['control']),joined)
        self.assertIn('no-new-privileges:true',command)
        self.assertIn('/usr/bin/env',command)
        for pair in [('agent','finalize'),('shell','run')]:
            with self.assertRaises(ValueError):driver.command(*pair,self.launcher.paths)
        with self.assertRaises(ValueError):DockerTransport({'agent':'latest','evaluator':'latest','mcp':'latest'},'/nonexistent/service.pgpass')
