"""Private, immutable run artifacts. No subprocesses or network access."""
import hashlib
import os
import secrets
import stat
from pathlib import Path

from contracts.validate import canonical_bytes, load_bytes, validate
from observability.jsonl import LogError, redact


class ArtifactError(ValueError):
    """Sanitized artifact boundary failure."""


class Artifacts:
    def __init__(self, root, *, secrets=(), max_bytes=100 * 1024**2):
        self.root = Path(root).absolute()
        self.secrets = tuple(secrets)
        self.max_bytes = min(max_bytes, 100 * 1024**2)
        self._control_slots = {}
        # Walk every ancestor without following symlinks, including the root.
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in self.root.parts[1:]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            info = os.fstat(fd)
            if stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
                raise ArtifactError('private_root')
        except OSError:
            raise ArtifactError('private_root') from None
        finally:
            os.close(fd)

    def _parent(self, path, create=False):
        validate('ArtifactRef', {'path': path, 'sha256': '0' * 64, 'bytes': 1})
        parts = path.split('/')
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                        os.fsync(fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
                info = os.fstat(fd)
                if stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
                    raise ArtifactError('private_directory')
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def size(self):
        total = 0
        for base, dirs, files in os.walk(self.root, followlinks=False):
            for name in dirs + files:
                info = os.lstat(Path(base) / name)
                if stat.S_ISLNK(info.st_mode):
                    raise ArtifactError('symlink')
                if stat.S_ISREG(info.st_mode):
                    total += info.st_size
                elif not stat.S_ISDIR(info.st_mode):
                    raise ArtifactError('file_type')
        return total

    def write(self, path, value, *, contract=None, private=False):
        if not private:
            try:
                value = redact(value, self.secrets)
            except LogError:
                raise ArtifactError('artifact_redaction') from None
        if contract:
            validate(contract, value)
        return self.write_bytes(path, canonical_bytes(value) + b'\n')

    def write_bytes(self, path, raw):
        if len(raw) > 1024**2 or not raw or self.size() + len(raw) > self.max_bytes:
            raise ArtifactError('artifact_limit')
        fd, name = self._parent(path, True)
        temporary = '.publish-' + secrets.token_hex(12)
        try:
            out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(out, 'wb') as stream:
                if stream.write(raw) != len(raw):
                    raise ArtifactError('short_write')
                stream.flush()
                os.fsync(stream.fileno())
            # link is atomic and cannot overwrite a prior finalized result.
            os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            os.fsync(fd)
        except OSError:
            raise ArtifactError('artifact_publish') from None
        finally:
            try:
                os.unlink(temporary, dir_fd=fd)
                os.fsync(fd)
            finally:
                os.close(fd)
        return {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

    def reserve_control_journal(self, phase):
        """Charge finite host-only evidence slots before admitting a child.

        This is application accounting, not a kernel quota on external writers.
        A later overshoot still fails the run; consuming a slot adds no bytes.
        """
        if phase not in {'prepare', 'settle-grade', 'finalize'}:
            raise ArtifactError('control_phase')
        for kind, capacity in (('exit', 64 * 1024), ('result', 1024**2)):
            target = f'journal/{phase}-{kind}.json'
            reserved = f'journal/reserved-{phase}-{kind}.json'
            self.write_bytes(reserved, b' ' * capacity)
            self._control_slots[target] = (reserved, capacity)

    def _consume_control_slot(self, path, raw):
        # Only typed, fixed-path callers below can consume these allocations.
        reserved, capacity = self._control_slots[path]
        if not raw or len(raw) > capacity:
            raise ArtifactError('control_slot_limit')
        directory, name = self._parent(reserved)
        destination = path.split('/')[-1]
        try:
            fd = os.open(name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, 'r+b') as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                        stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size != capacity):
                    raise ArtifactError('control_slot')
                if stream.write(raw) != len(raw):
                    raise ArtifactError('short_write')
                stream.truncate(len(raw))
                stream.flush()
                os.fsync(stream.fileno())
            # As with ordinary artifacts, never replace prior finalized evidence.
            os.link(name, destination, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            os.unlink(name, dir_fd=directory)
            os.fsync(directory)
            del self._control_slots[path]
        except OSError:
            raise ArtifactError('control_publish') from None
        finally:
            os.close(directory)

    def publish_control_exit(self, record):
        record = redact(record, self.secrets)
        validate('ProcessExit', record)
        if record['child'] != 'evaluator':
            raise ArtifactError('control_child')
        self._consume_control_slot(f'journal/{record["phase"]}-exit.json', canonical_bytes(record) + b'\n')

    def publish_control_result(self, raw, record):
        """Retain exact validated bytes correlated to the already journaled exit."""
        validate('ProcessExit', record)
        result = load_bytes(raw)
        validate('ControlResult', result)
        if (record['child'] != 'evaluator' or record['result_delivery'] != 'complete' or
                any(record[k] != result[k] for k in
                    ('schema_version', 'run_id', 'attempt_id', 'task_id', 'task_hash', 'config_hash', 'phase')) or
                record['result_message_id'] != result['message_id'] or
                record['result_ref']['path'] != f'control/{record["phase"]}-result.json' or
                record['result_ref']['sha256'] != hashlib.sha256(raw).hexdigest() or
                record['result_ref']['bytes'] != len(raw)):
            raise ArtifactError('control_binding')
        if self.load(f'journal/{record["phase"]}-exit.json', 'ProcessExit') != record:
            raise ArtifactError('control_exit')
        self._consume_control_slot(f'journal/{record["phase"]}-result.json', raw)

    def read(self, ref, contract=None):
        validate('ArtifactRef', ref)
        fd, name = self._parent(ref['path'])
        try:
            source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(source, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                    raise ArtifactError('private_file')
                raw = stream.read(1024**2 + 1)
            if len(raw) > 1024**2 or len(raw) != ref['bytes'] or hashlib.sha256(raw).hexdigest() != ref['sha256']:
                raise ArtifactError('artifact_integrity')
            value = load_bytes(raw)
            if contract:
                validate(contract, value)
            return value
        except OSError:
            raise ArtifactError('artifact_read') from None
        finally:
            os.close(fd)

    def manifest(self, path='evidence/manifest.json'):
        rows = []
        self.size()
        for base, _, files in os.walk(self.root, followlinks=False):
            for name in sorted(files):
                item = Path(base) / name
                relative = item.relative_to(self.root).as_posix()
                raw = item.read_bytes()
                rows.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        return self.write(path, {'schema_version': 1, 'artifacts': sorted(rows, key=lambda x: x['path'])}, private=True)

    def reference(self, path):
        """Capture exact existing bytes from a trusted fixed artifact path."""
        fd, name = self._parent(path)
        try:
            source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(source, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                    raise ArtifactError('private_file')
                raw = stream.read(1024**2 + 1)
            ref = {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            self.read(ref)  # strict JSON, owner/mode, cap and integrity checks
            return ref
        finally:
            os.close(fd)

    def load(self, path, contract=None):
        return self.read(self.reference(path), contract)

    def read_jsonl(self, path):
        fd, name = self._parent(path)
        try:
            source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            rows = []
            with os.fdopen(source, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
                    raise ArtifactError('private_trace')
                if self.size() > self.max_bytes:
                    raise ArtifactError('artifact_limit')
                while True:
                    line = stream.readline(1024**2 + 1)
                    if not line:
                        break
                    if len(line) > 1024**2 or not line.endswith(b'\n') or len(rows) >= 10000:
                        raise ArtifactError('trace_limit')
                    value = load_bytes(line)
                    validate('Event', value)
                    rows.append(value)
            return rows
        finally:
            os.close(fd)
