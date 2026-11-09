"""Fixed Docker child transport. Construct only after the operator runtime gate.

This module performs no runtime work on import. It never uses a shell, tag,
Compose teardown, volume deletion, credential argument, or model-provided path.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request


@dataclass(frozen=True)
class Outcome:
    returncode: int | None
    reaped: bool
    termination: str
    signal: str | None
    ended_monotonic: float


class DockerTransport:
    def __init__(self, images, service_passfile):
        if set(images) != {'agent','evaluator','mcp'} or any(not re.fullmatch(r'sha256:[0-9a-f]{64}',v) for v in images.values()):
            raise ValueError('frozen_image_ids_required')
        self.images = dict(images)
        self.service_passfile=Path(service_passfile).absolute()
        self.service_id=None
        self.service_run=None

    def start_mcp(self,paths,deadline,quota):
        run=str(paths['mcp-control'])
        if self.service_id is not None:
            if self.service_run!=run:raise ValueError('service_run_reuse')
            return
        args=['docker','run','--detach','--pull','never','--user','1000:1000',
              '--cap-drop','ALL','--security-opt','no-new-privileges:true','--read-only',
              '--memory','256m','--memory-swap','256m','--cpus','0.5','--pids-limit','128',
              '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16777216,mode=1777',
              '--log-driver','local','--log-opt','max-size=1m','--log-opt','max-file=1','--log-opt','compress=false',
              '--network','mcpbench_db','--publish','127.0.0.1:18081:8080']
        args+=self.mount(self.service_passfile,'/run/secrets/service.pgpass')
        args+=self.mount(paths['mcp-control'],'/run/mcpbench/trace')
        args+=self.mount(paths['mcp-output']/'trace','/run/mcpbench/events',False)
        args+=[self.images['mcp']]
        raw=subprocess.run(args,check=True,capture_output=True,timeout=max(.001,deadline-time.monotonic()),env={'PATH':os.environ['PATH']}).stdout
        cid=raw.decode().strip()
        if not re.fullmatch(r'[0-9a-f]{64}',cid):raise ValueError('service_identity')
        self.service_id,self.service_run=cid,run
        self.receipt(paths['control']/'mcp-container.json',cid)
        client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while time.monotonic()<deadline:
            quota()
            try:
                with client.open('http://127.0.0.1:18081/healthz',timeout=min(1,max(.001,deadline-time.monotonic()))) as response:
                    if response.status==200 and response.read(64)==b'ready\n':return
            except Exception:pass
            time.sleep(min(.02,max(0,deadline-time.monotonic())))
        raise TimeoutError('service_health')

    @staticmethod
    def receipt(path,cid):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as out:
            out.write(json.dumps({'container_id':cid}).encode());out.flush();os.fsync(out.fileno())

    def close(self,paths,timeout):
        if self.service_id is None:return
        cid=self.service_id
        deadline=time.monotonic()+timeout
        def call(args):
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('service_close_deadline')
            return subprocess.run(args,check=True,capture_output=True,timeout=remaining,env={'PATH':os.environ['PATH']})
        # Exact fresh CID only. Preserve complete bounded logs privately before
        # removing this container. No volumes flag or project teardown exists.
        call(['docker','stop','--time','1',cid])
        state=json.loads(call(['docker','inspect','--format','{{json .State}}',cid]).stdout)
        if state['Running'] or state['Status']!='exited' or state['ExitCode']!=0:raise ValueError('service_exit')
        raw=call(['docker','logs',cid])
        data=raw.stdout+raw.stderr
        if len(data)>1024**2:raise ValueError('service_log_limit')
        target=paths['control']/'mcp.stderr'
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        call(['docker','rm',cid])
        self.service_id=None

    @staticmethod
    def mount(source,target,readonly=True):
        source = str(Path(source).absolute())
        if any(x in source for x in ',\n\r'):
            raise ValueError('mount_path')
        return ['--mount',f'type=bind,src={source},dst={target}'+(',readonly' if readonly else '')]

    def command(self, child, phase, paths):
        if (child,phase) not in {('agent','run'),('verifier','verify'),('evaluator','prepare'),('evaluator','settle-grade'),('evaluator','finalize')}:
            raise ValueError('fixed_child_phase')
        is_agent = child in {'agent','verifier'}
        flags = ['docker','create','--pull','never','--user','1000:1000','--cap-drop','ALL',
                 '--security-opt','no-new-privileges:true','--read-only',
                 '--memory','512m','--memory-swap','512m','--cpus','1' if is_agent else '0.5',
                 '--pids-limit','128','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16777216,mode=1777',
                 '--log-driver','local','--log-opt','max-size=1m','--log-opt','max-file=1','--log-opt','compress=false',
                 '--network','host' if is_agent else 'mcpbench_db']
        if is_agent:
            for name,target in [('request.json','/run/mcpbench/request.json'),('auth.json','/run/secrets/auth.json')]:
                flags += self.mount(paths[child+'-input']/'transport'/name,target)
            flags += self.mount(paths[child+'-output']/'transport','/run/mcpbench/output',False)
            flags += ['--entrypoint','/usr/bin/env',self.images['agent'],'-i',
                      'PATH=/usr/local/bin:/usr/bin:/bin','LANG=C.UTF-8','TZ=UTC','HOME=/nonexistent','TMPDIR=/tmp',
                      '/app/agent',phase,'--request','/run/mcpbench/request.json','--auth','/run/secrets/auth.json',
                      '--output','/run/mcpbench/output']
        else:
            flags += self.mount(paths['control'],'/run/mcpbench/control')
            flags += self.mount(paths['evaluator'],'/run/mcpbench/output',False)
            flags += ['--env','PGHOST=db','--env','PGDATABASE=mcpbench',self.images['evaluator'],phase]
        return flags

    def execute(self,child,phase,paths,timeout,quota):
        deadline=time.monotonic()+timeout
        if child=='agent':self.start_mcp(paths,deadline,quota)
        # Daemon operations also consume the same startup/transport deadline.
        def bounded(args):
            remaining=deadline-time.monotonic()
            if remaining<=0: raise TimeoutError('child_deadline')
            return subprocess.run(args,check=True,capture_output=True,timeout=remaining,
                                  env={'PATH':os.environ['PATH']}).stdout
        cid=None
        process=None
        ended=None
        try:
            cid=bounded(self.command(child,phase,paths)).decode().strip()
            if not re.fullmatch(r'[0-9a-f]{64}',cid):raise ValueError('container_identity')
            self.receipt(paths['control']/f'{child}-{phase}-container.json',cid)
            log=paths['control']/f'{child}-{phase}.stderr'
            fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as error:
                process=subprocess.Popen(['docker','start','--attach',cid],stdin=subprocess.DEVNULL,
                    stdout=error,stderr=error,env={'PATH':os.environ['PATH']})
                while process.poll() is None:
                    quota()
                    if time.monotonic()>=deadline:raise TimeoutError('child_deadline')
                    time.sleep(min(.02,max(0,deadline-time.monotonic())))
                ended=time.monotonic()
            state=json.loads(bounded(['docker','inspect','--format','{{json .State}}',cid]))
            if state['Running'] or state['Status']!='exited':raise ValueError('child_not_reaped')
            code=state['ExitCode']
            # Reap and remove only this verified one-shot child; no volumes flag.
            bounded(['docker','rm',cid])
            return Outcome(code,True,'exited',None,ended)
        except BaseException:
            # Do not turn uncertain daemon/process completion into positive reap
            # evidence. Exact-CID cancellation is best effort within the original
            # deadline; failure forces durable launcher quarantine.
            if cid and re.fullmatch(r'[0-9a-f]{64}',cid):
                try:bounded(['docker','kill','--signal','KILL',cid])
                except Exception:pass
            if process is not None and process.poll() is None:
                process.kill();process.wait(timeout=1)
            return Outcome(None,False,'spawn_failed' if cid is None else 'timed_out',None,ended or time.monotonic())
