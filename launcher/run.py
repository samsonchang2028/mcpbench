"""Typed evaluator/child transport with durable no-retry quarantine.

Only trusted operator code constructs a transport. No executable, endpoint,
image, mount or backend selection is accepted from model arguments.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
import time

from contracts.validate import canonical_bytes, canonical_hash, load_bytes, validate, validate_event_stream
from eval.runner.artifacts import Artifacts

LIMIT = 100 * 1024**2


def utc(value):
    return value.isoformat(timespec='microseconds').replace('+00:00', 'Z')


class Launcher:
    def __init__(self, parent, transport, *, monotonic=time.monotonic,
                 wall=lambda: datetime.now(timezone.utc)):
        self.parent, self.transport = Path(parent).absolute(), transport
        self.mono, self.wall = monotonic, wall
        self.root = None
        self.anchor = None
        self.floor = 0
        self.chain = dict(requests=[],results=[],exits=[],verifier=None,verification_request=None,agent_result=None)

    def budget(self):
        if self.anchor is None:
            return None
        elapsed = max(self.floor, math.ceil(max(0, self.mono() - self.anchor) * 1000))
        self.floor = elapsed
        remaining = max(0, 30000-elapsed)
        value = dict(anchor_id='post-' + self.run_id.removeprefix('run-'),
                     started_at=utc(self.anchor_wall), deadline_at=utc(self.anchor_wall + timedelta(seconds=30)),
                     elapsed_ms=elapsed, remaining_ms=remaining, operation_timeout_ms=min(5000, remaining))
        validate('PostAgentBudget', value)
        return value

    def remaining(self, default):
        value = self.budget()
        remaining = default if value is None else min(default, value['remaining_ms']/1000)
        if remaining <= 0:
            raise ValueError('post_agent_expired')
        return remaining

    def quota(self):
        total = 0
        for base, dirs, files in os.walk(self.root, followlinks=False):
            for name in dirs + files:
                p = Path(base)/name
                if p.is_symlink():
                    raise ValueError('artifact_symlink')
                info = p.stat()
                if p.is_file():
                    total += info.st_size
                elif not p.is_dir():
                    raise ValueError('artifact_type')
        if total > LIMIT:
            raise ValueError('artifact_limit')
        return total

    def fixed_transport(self, name, raw):
        # request.json/result.json are transport slots, not immutable evidence.
        # Every delivered byte also has an immutable evaluator ArtifactRef.
        target = self.paths['control']/name
        temporary = target.with_name('.' + name)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(raw); out.flush(); os.fsync(out.fileno())
            os.replace(temporary, target)
            directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
        self.quota()

    def copy(self, source, destination, path, kind=None):
        ref = source.reference(path)
        value = source.read(ref, kind)
        # Exact original bytes, never a reserialization that changes the hash.
        raw = (source.root/path).read_bytes()
        copied = destination.write_bytes(path, raw)
        if ref != copied:
            raise ValueError('transport_hash')
        return copied, value

    def request(self, phase, prior=None, extra=None):
        inputs = deepcopy(self.initial) if phase == 'prepare' else {
            'prior_phase_result': self.files.reference(f'control/{prior["phase"]}-result.json'), **(extra or {})}
        request = dict(**self.identity, phase=phase, budget=self.budget(), inputs=inputs,
                       message_id=phase+'-'+self.run_id.removeprefix('run-'),
                       prior_result_id=None if prior is None else prior['message_id'])
        validate('ControlRequest', request)
        self.host.write(f'journal/{phase}-request.json', request, private=True)
        self.fixed_transport('request.json', canonical_bytes(request)+b'\n')
        self.quota()
        start=self.mono()
        outcome = self.transport.execute('evaluator', phase, self.paths, self.remaining(30 if phase=='prepare' else 5), self.quota)
        self.quota()
        if not outcome.reaped or outcome.returncode != 0 or outcome.termination != 'exited':
            raise ValueError('evaluator_transport')
        ref = self.files.reference(f'control/{phase}-result.json')
        result = self.files.read(ref, 'ControlResult')
        if any(result[k] != self.identity[k] for k in self.identity) or result['request_id'] != request['message_id']:
            raise ValueError('evaluator_identity')
        if result['phase'] != phase:
            raise ValueError('evaluator_phase')
        budget = result['budget']
        if self.anchor is not None:
            current = self.budget()
            if any(budget[k] != current[k] for k in ('anchor_id','started_at','deadline_at')) or budget['elapsed_ms'] < request['budget']['elapsed_ms'] or budget['elapsed_ms'] > current['elapsed_ms']:
                raise ValueError('budget_transport')
            self.floor = max(self.floor, budget['elapsed_ms'])
            self.remaining(30)
        raw = (self.files.root/ref['path']).read_bytes()
        self.fixed_transport('result.json', raw)
        self.host.write_bytes(f'journal/{phase}-result.json', raw)
        record=dict(**self.identity,producer='launcher',child='evaluator',phase=phase,
                    termination=outcome.termination,exit_code=outcome.returncode,signal=outcome.signal,
                    result_delivery='complete',result_ref=ref,duration_ms=math.ceil(max(0,outcome.ended_monotonic-start)*1000),
                    budget=self.budget(),result_message_id=result['message_id'],reaped=outcome.reaped)
        record.pop('workflow_kind')
        validate('ProcessExit',record)
        self.host.write(f'journal/{phase}-exit.json',record,contract='ProcessExit')
        self.chain['requests'].append(request);self.chain['results'].append(result);self.chain['exits'].append(record)
        self.quota()
        if result['action'] in {'quarantine','blocked'}:
            raise ValueError('evaluator_quarantine')
        return result

    def trace(self, source, path, *, combined=None):
        rows = source.read_jsonl(path)
        if not rows or any((e['run_id'],e['attempt_id']) != (self.run_id,self.attempt) for e in rows):
            raise ValueError('trace_identity')
        validate_event_stream(rows if combined is None else combined+rows)
        return rows, (source.root/path).read_bytes()

    def child(self, kind, request_ref, auth_path):
        inputs = Artifacts(self.paths[kind+'-input'])
        source_ref = self.files.reference(request_ref['path'])
        if source_ref != request_ref:
            raise ValueError('request_binding')
        request = self.files.read(request_ref, 'AgentRequest' if kind=='agent' else 'VerificationRequest')
        auth = self.files.load(auth_path, 'AuthInput')
        if (auth['run_id'],auth['attempt_id'],auth['mode']) != (self.run_id,self.attempt,'agent' if kind=='agent' else 'verify'):
            raise ValueError('auth_binding')
        self.secrets.append(auth['capability'])
        if kind=='verifier':self.chain['verification_request']=request
        inputs.secrets = tuple(self.secrets)
        inputs.write_bytes('transport/request.json', (self.files.root/request_ref['path']).read_bytes())
        inputs.write_bytes('transport/auth.json', (self.files.root/auth_path).read_bytes())
        self.trace_control('execution' if kind=='agent' else 'verification')
        start = self.mono()
        outcome = self.transport.execute(kind, 'run' if kind=='agent' else 'verify', self.paths,
                                         self.remaining(300 if kind=='agent' else 5), self.quota)
        ended = outcome.ended_monotonic
        if not start <= ended <= self.mono():
            raise ValueError('process_clock')
        if kind=='agent':
            self.anchor = ended
            self.anchor_wall = self.wall()-timedelta(seconds=max(0,self.mono()-ended))
            self.host.write('journal/post-agent-anchor.json', self.budget(), private=True)
        self.quota()
        output = Artifacts(self.paths[kind+'-output'])
        result_ref = None
        delivery = 'missing'
        try:
            os.lstat(output.root/'transport/result.json')
            ref = output.reference('transport/result.json')
            delivered=output.read(ref, 'AgentResult' if kind=='agent' else 'VerifierResult')
            self.chain['agent_result' if kind=='agent' else 'verifier']=delivered
            raw = (output.root/ref['path']).read_bytes()
            result_ref = self.files.write_bytes(f'{kind}/result.json', raw)
            delivery = 'complete'
        except FileNotFoundError:
            pass
        except Exception:
            delivery = 'malformed'
        record = dict(**self.identity, producer='launcher', child=kind,
                      phase='run' if kind=='agent' else 'verify', termination=outcome.termination,
                      exit_code=outcome.returncode if outcome.returncode is not None and outcome.returncode>=0 else None,
                      signal=outcome.signal, result_delivery=delivery, result_ref=result_ref,
                      duration_ms=math.ceil(max(0, ended-start)*1000),
                      budget=None if kind=='agent' else self.budget(), result_message_id=None, reaped=outcome.reaped)
        # ProcessExit has no workflow_kind (ControlRequest's identity does).
        record.pop('workflow_kind')
        validate('ProcessExit',record)
        exit_ref = self.files.write(f'{kind}/exit.json',record,contract='ProcessExit')
        self.chain['exits'].append(record)
        if not outcome.reaped:
            raise ValueError('unreaped_child')
        extra = {kind+'_exit':exit_ref}
        if result_ref is not None:
            extra[kind+'_result'] = result_ref
        return extra, output

    def trace_control(self, phase):
        target = Artifacts(self.paths['mcp-control'])
        raw = canonical_bytes(dict(schema_version=1,run_id=self.run_id,attempt_id=self.attempt,
                                   phase=phase,secrets=self.secrets))+b'\n'
        # Trusted atomic phase slot. Persist immutable copies in the host journal.
        self.host.write_bytes(f'journal/mcp-{phase}.json',raw)
        path = target.root/'config.json'
        temporary = target.root/'.config.json'
        fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
        fd = os.open(target.root,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def run(self, task, fixture, config, control_files):
        mapping = config['mapping']
        self.run_id,self.attempt = mapping['run_id'],mapping['attempt_id']
        validate('Identifier',self.run_id);validate('Identifier',self.attempt)
        if config['trace_paths'] != ['events/agent.jsonl','events/mcp.jsonl']:
            raise ValueError('fixed_trace_paths')
        # Existing attempts, including incomplete/quarantined attempts, are never
        # replayed. The exclusive directory is the durable restart barrier.
        Artifacts(self.parent)  # verify owner-only, symlink-free trusted run parent
        self.root = self.parent/self.run_id
        self.root.mkdir(mode=0o700)
        self.host = Artifacts(self.root)
        self.host.write('journal/entered.json',dict(schema_version=1,incomplete_until_complete=True,reset_or_reuse=False),private=True)
        self.paths = {key:self.root/key for key in ('control','evaluator','agent-input','agent-output',
                      'verifier-input','verifier-output','mcp-control','mcp-output')}
        for path in self.paths.values(): path.mkdir(mode=0o700)
        (self.paths['mcp-output']/'trace').mkdir(mode=0o700)
        for key in ('agent-input','agent-output','verifier-input','verifier-output'):
            (self.paths[key]/'transport').mkdir(mode=0o700)
        self.files = Artifacts(self.paths['evaluator'])
        if hasattr(self.transport,'metadata'):self.host.write('journal/transport.json',self.transport.metadata,private=True)
        self.secrets = []
        try:
            if set(control_files) != {'database.json','controller.pgpass','grader.pgpass'}:
                raise ValueError('private_control_files')
            for name,raw in control_files.items(): self.fixed_transport(name,raw)
            self.identity = dict(schema_version=1,run_id=self.run_id,attempt_id=self.attempt,
                task_id=task['task_id'],task_hash=canonical_hash(task),config_hash=canonical_hash(config),
                workflow_kind=task['expected_state']['kind'])
            self.initial = {key:self.files.write('input/'+key+'.json',value,private=True) for key,value in
                            (('task',task),('fixture',fixture),('config',config))}
            prepared = self.request('prepare')
            if prepared['action'] != 'execute_agent': raise ValueError('prepare_decision')
            agent_inputs,agent_output = self.child('agent',prepared['outputs']['agent_request'],'private/agent-auth.json')
            # Missing/invalid original traces must not bypass the evaluator's
            # first fence. Preserve exact available bytes (or an explicit empty
            # stream for unavailable evidence), then settle before quarantining.
            trace_error=False
            mcp_files=Artifacts(self.paths['mcp-output'])
            for source,path,target in ((agent_output,'transport/events.jsonl','events/agent.jsonl'),
                                       (mcp_files,'trace/events.jsonl','events/mcp.jsonl')):
                raw=b'\n'
                try:
                    directory,name=source._parent(path)
                    try:
                        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
                        with os.fdopen(fd,'rb') as stream:
                            info=os.fstat(stream.fileno())
                            import stat
                            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600 or info.st_uid!=os.getuid():raise ValueError('private_trace')
                            raw=stream.read(1024**2+1)
                            if len(raw)>1024**2:raise ValueError('trace_limit')
                    finally:os.close(directory)
                    if not raw:raw=b'\n'
                except Exception:
                    raw=b'\n';trace_error=True
                self.files.write_bytes(target,raw)
            try:
                rows=self.files.read_jsonl('events/agent.jsonl')+self.files.read_jsonl('events/mcp.jsonl')
                validate_event_stream(rows)
                if not rows or any((e['run_id'],e['attempt_id'])!=(self.run_id,self.attempt) for e in rows):raise ValueError('trace_scope')
            except Exception:trace_error=True
            settled = self.request('settle-grade',prepared,agent_inputs)
            if trace_error:raise ValueError('original_trace_incomplete')
            verifier_inputs = {}
            if settled['action'] == 'verify':
                verifier_inputs,verifier_output=self.child('verifier',settled['outputs']['verification_request'],'private/verify-auth.json')
                _,raw=self.trace(verifier_output,'transport/events.jsonl')
                self.files.write_bytes('events/verifier.jsonl',raw)
                # One continuous MCP writer; preserve the original snapshot and
                # validate the final full MCP source separately from verifier's
                # separately started agent source. Never renumber raw evidence.
                _,raw=self.trace(mcp_files,'trace/events.jsonl')
                self.files.write_bytes('events/mcp-final.jsonl',raw)
            elif settled['action'] != 'finalize': raise ValueError('settle_decision')
            self.quota()
            final = self.request('finalize',settled,verifier_inputs)
            if final['action'] != 'complete': raise ValueError('final_decision')
            validate('ControlChain',self.chain)
            self.host.write('journal/control-chain.json',self.chain,contract='ControlChain')
            if hasattr(self.transport,'close'):self.transport.close(self.paths,self.remaining(5))
            self.quota()
            self.remaining(30)
            self.host.write('journal/complete.json',{'schema_version':1,'result':final},private=True)
            return final
        except BaseException:
            try:
                self.host.write('journal/quarantine.json',{'schema_version':1,'reason':'launcher_incomplete','reset_or_reuse':False},private=True)
            except Exception:
                pass  # durable entered.json already forbids retry/reset/reuse
            raise ValueError('launcher quarantined') from None
