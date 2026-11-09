"""Fixed private evaluator entrypoint; no child execution or plugin loading."""
import os
from pathlib import Path
import stat
import sys

from contracts.validate import load_bytes, validate
from .artifacts import Artifacts
from .lifecycle import Evaluator

CONTROL = Path('/run/mcpbench/control')
OUTPUT = Path('/run/mcpbench/output')


def read_request(control=CONTROL):
    # Walk the fixed transport ancestors, rejecting every symlink.
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in Path(control).absolute().parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open('request.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
                raise ValueError('private_request')
            raw = stream.read(1024**2 + 1)
        if len(raw) > 1024**2:
            raise ValueError('request_limit')
        request = load_bytes(raw)
        validate('ControlRequest', request)
        return request
    finally:
        os.close(directory)


def main(argv=None, *, backend=None, root=OUTPUT, control=CONTROL):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in {'prepare', 'settle-grade', 'finalize'}:
        print('mcpbench: expected fixed evaluator phase', file=sys.stderr)
        return 2
    try:
        files = Artifacts(root)
        request = read_request(control)
        if request['phase'] != args[0]:
            raise ValueError('phase')
        if backend is None:
            from db.lifecycle import PostgresBackend
            backend = PostgresBackend.from_private_config(str(CONTROL / 'database.json'))
        files.secrets += tuple(getattr(backend, 'known_secrets', ()))
        result = Evaluator(files, backend).invoke(request)
        # Trusted host copies/hashes this phase-specific file to the fixed private
        # control/result.json transport path; output remains writable-only scope.
        return 0 if result['action'] not in {'blocked', 'quarantine'} else 1
    except Exception:
        print('mcpbench: evaluator phase failed; quarantine required', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
