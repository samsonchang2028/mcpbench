"""Admitted deterministic T019 entrypoint. Never calls the native model service."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from contracts.validate import load_bytes, load_file, validate
from eval.runner.artifacts import Artifacts
from .run import Launcher, utc
from .transport import DockerTransport

ROOT=Path(__file__).resolve().parents[1]


def private_bytes(path):
    path=Path(path).absolute()
    Artifacts(path.parent)  # owner-only and no symlink in any ancestor
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600 or info.st_uid!=os.getuid():
            raise ValueError('private_file')
        raw=stream.read(1024**2+1)
    if not raw or len(raw)>1024**2:raise ValueError('private_limit')
    return raw


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if len(args)!=2 or args[0]!='--config':
        print('mcpbench: expected private launcher config',file=sys.stderr);return 2
    try:
        config=load_bytes(private_bytes(args[1]))
        if set(config)!={'schema_version','images','service_passfile','control_source','artifacts_parent','scenario'} or config['schema_version']!=1:
            raise ValueError('launch_config')
        scenario=config['scenario']
        if scenario not in {'smoke','wrong-write','lost-reply'}:raise ValueError('scripted_scenario')
        for key in ('service_passfile','control_source','artifacts_parent'):
            if type(config[key]) is not str or not Path(config[key]).is_absolute():raise ValueError('fixed_paths')
        # Validate the service-only credential's file boundary without reading or
        # copying its bytes into the evaluator or agent input trees.
        service=Path(config['service_passfile']);Artifacts(service.parent)
        info=service.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600 or info.st_uid!=os.getuid():raise ValueError('service_credential')
        control={name:private_bytes(Path(config['control_source'])/name) for name in ('database.json','controller.pgpass','grader.pgpass')}
        task=load_file(ROOT/'eval/fixtures/v1/tasks/smoke-invoice.json')
        fixture=load_file(ROOT/'eval/fixtures/v1/fixture.json')
        run_id='run-'+secrets.token_hex(12);attempt='attempt-'+secrets.token_hex(12)
        mapping=dict(schema_version=1,run_id=run_id,attempt_id=attempt,tenant_id=fixture['tenant_id'],
            principal_id=task['principal_id'],allowed_tools=task['permitted_tools'],
            schema_name='r_'+hashlib.sha256(run_id.encode()).hexdigest()[:32],phase='prepared',generation=0,
            not_after=utc(datetime.now(timezone.utc)+timedelta(seconds=300)),agent_token_sha256=None,
            verifier_token_sha256=None,verifier_scope=None,lock_marker=0,workflow_kind='draft_invoice')
        validate('RunMapping',mapping)
        script=(ROOT/'tests/integration/scripted-agent/main.go').read_bytes()
        model=dict(tag='scripted-t019-'+scenario,digest=hashlib.sha256(script+scenario.encode()).hexdigest(),
                   context_tokens=4096,output_tokens=512,temperature=0,seed=None,think=None,keep_alive=None)
        runtime=dict(mapping=mapping,idempotency_key='idem-'+secrets.token_hex(12),model=model,
                     trace_paths=['events/agent.jsonl','events/mcp.jsonl'])
        driver=DockerTransport(config['images'],service)
        driver.metadata=dict(images=config['images'],scenario=scenario,scripted=True,native_inference=False)
        launcher=Launcher(config['artifacts_parent'],driver)
        result=launcher.run(task,fixture,runtime,control)
        evaluation=Artifacts(launcher.paths['evaluator']).read(result['outputs']['evaluation'],'EvaluationResult')
        expected_original=scenario!='wrong-write'
        if result['original_pass']!=expected_original or not evaluation['comparison_valid']:
            raise ValueError('integration_assertions')
        print(json.dumps(dict(run_id=run_id,scenario=scenario,original_pass=result['original_pass'],
                              comparison_valid=evaluation['comparison_valid'],native_inference=False)))
        return 0
    except Exception:
        print('mcpbench: integration failed; preserve attempt and inspect quarantine',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
