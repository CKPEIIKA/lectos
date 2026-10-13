# Security and reliability checklist

Apply only the items matching boundaries the project actually owns. Record concrete limits and failure behavior in project documentation; do not claim controls for features that do not exist.

## Filesystem and CLI

- Resolve user-supplied paths against an explicit input or output root and reject traversal outside it.
- Decide whether symlinks are allowed. Check the resolved target before destructive or privileged operations.
- Do not overwrite existing user data unless the command explicitly promises it and the user selected that behavior.
- Use securely created temporary files and atomic replacement for durable output when practical.
- Bound file, archive, line, and decoded-object sizes before loading them fully into memory.
- Extract archives member by member only after rejecting absolute paths, parent traversal, links, devices, and other unsupported entry types.
- Pass subprocess arguments as a sequence with `shell=False`; use an absolute or deliberately resolved executable where trust matters.
- Control subprocess working directory, environment, stdin, output capture, timeout, and exit-status handling.
- Use safe, data-only formats for untrusted input. Never load an untrusted pickle or enable unsafe YAML/object constructors.
- Send primary output to stdout, diagnostics to stderr, and return stable nonzero exit statuses for failures.

## Timeouts, cancellation, and resources

- Give every network request, subprocess, lock acquisition, and external-service wait a finite timeout.
- Document whether a timeout covers connection, individual reads, or the whole operation.
- Bound concurrency, queues, retry attempts, backoff, input sizes, captured output, and retained results.
- Retry only transient failures for operations known to be idempotent; preserve the final cause.
- On cancellation, `KeyboardInterrupt`, timeout, or partial failure, terminate owned child processes and close files, locks, sockets, and temporary resources.
- Do not catch cancellation or interrupts merely to continue normal work.

## Required project tests

- Test path traversal and symlink behavior for commands that read, write, extract, or delete.
- Test subprocess arguments, nonzero exits, timeout, and cleanup when the project launches processes.
- Test external-service timeout, cancellation, retry exhaustion, and partial response behavior when such integrations exist.
- Test configured size and concurrency limits at the boundary and immediately beyond it.
- Prefer deterministic fakes over sleeps; mark unavoidable real integration tests explicitly.
