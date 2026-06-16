import os
import re
import resource
import select
import shlex
import signal
import subprocess
import sys
import time


FLAG = os.environ.get("FLAG", "ctf4b{dummy_flag}")
MAX_COMMAND_BYTES = 300
MAX_OUTPUT_BYTES = 4096
TIMEOUT_SECONDS = 3
READ_CHUNK_BYTES = 1024

MEMORY_LIMIT_BYTES = 128 * 1024 * 1024
FILE_SIZE_LIMIT_BYTES = 1024 * 1024
MAX_PROCESSES = 64
MAX_OPEN_FILES = 32

BANNER = """== greenroom ==
The previous coding agent ran `env`.
The user was not happy.
Some Bash tool calls are now denied.

Submit one Bash command."""

DENY_TOKENS = [
    "$(",
    "`",
    "|",
    "<(",
    ">(",
    "/usr",
]

DENIED_COMMANDS = {
    "env",
    "printenv",
    "cat",
    "tr",
    "grep",
    "sed",
    "awk",
    "od",
    "strings",
    "xxd",
    "dd",
    "base64",
    "python",
    "python3",
    "perl",
    "ruby",
    "node",
    "bash",
    "sh",
    "source",
    "eval",
    "exec",
    "command",
    "set",
    "export",
    "declare",
    "typeset",
    "readonly",
    "compgen",
    "coproc",
    "jobs",
    "fg",
    "bg",
    "disown",
}

SHELL_KEYWORDS = {
    "!",
    "{",
    "}",
    "case",
    "do",
    "done",
    "elif",
    "else",
    "esac",
    "fi",
    "for",
    "if",
    "in",
    "then",
    "time",
    "until",
    "while",
}

COMMAND_START_KEYWORDS = {
    "!",
    "{",
    "do",
    "elif",
    "else",
    "for",
    "if",
    "then",
    "time",
    "until",
    "while",
}

COMMAND_SEPARATORS = {";", "&", "&&", "||", "\n"}
REDIRECT_OPERATORS = {
    "<",
    ">",
    ">|",
    ">>",
    "<>",
    "<<",
    "<<-",
    "<<<",
    "&>",
    "&>>",
}

ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?=.*", re.DOTALL)
REDIRECT_RE = re.compile(r"^(?:[0-9]+)?(?:<|>|>>|<>|<<|<<-|<<<|&>|&>>|>\|)")
BIN_PATH_RE = re.compile(r"(^|[\s;&(])(/bin)(?=$|[/?\s;&)])")

PROLOGUE = "enable -n set export declare typeset readonly compgen source . eval exec command hash enable; "
BASH = ["/bin/bash", "--restricted", "--noprofile", "--norc", "-c"]


def tokenize(cmd):
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def is_redirect(token):
    return token in REDIRECT_OPERATORS or REDIRECT_RE.match(token) is not None


def is_assignment(token):
    return ASSIGNMENT_RE.match(token) is not None


def command_name(token):
    if "/" in token:
        return token
    return os.path.basename(token)


def deny_by_text(cmd):
    for token in DENY_TOKENS:
        if token in cmd:
            return token
    if BIN_PATH_RE.search(cmd):
        return "/bin"
    return None


def policy_check(cmd):
    denied = deny_by_text(cmd)
    if denied is not None:
        return denied

    try:
        tokens = tokenize(cmd)
    except ValueError:
        return None

    expect_command = True
    skip_redirection_target = False

    for token in tokens:
        if token == "&":
            return token

        if token in COMMAND_SEPARATORS:
            expect_command = True
            skip_redirection_target = False
            continue

        if skip_redirection_target:
            skip_redirection_target = False
            continue

        if is_redirect(token):
            skip_redirection_target = token in REDIRECT_OPERATORS
            continue

        if not expect_command:
            continue

        if token in SHELL_KEYWORDS:
            expect_command = token in COMMAND_START_KEYWORDS
            continue

        if is_assignment(token):
            continue

        command = command_name(token)
        if command in DENIED_COMMANDS:
            return command

        expect_command = False

    return None


def build_child_env():
    return {
        "PATH": "/app/bin",
        "HOME": "/tmp",
        "LC_ALL": "C",
        "TERM": "dumb",
        "AGENT": "greenroom",
        "MODE": "sandbox",
        FLAG: "x",
    }


def set_child_limits():
    set_limit(resource.RLIMIT_AS, MEMORY_LIMIT_BYTES)
    set_limit(resource.RLIMIT_CPU, TIMEOUT_SECONDS + 1)
    set_limit(resource.RLIMIT_FSIZE, FILE_SIZE_LIMIT_BYTES)
    set_limit(resource.RLIMIT_NOFILE, MAX_OPEN_FILES)

    if hasattr(resource, "RLIMIT_NPROC"):
        set_limit(resource.RLIMIT_NPROC, MAX_PROCESSES)


def set_limit(limit_kind, soft_limit):
    try:
        current_soft, current_hard = resource.getrlimit(limit_kind)
        if current_hard == resource.RLIM_INFINITY:
            hard_limit = soft_limit
        else:
            hard_limit = min(current_hard, soft_limit)

        resource.setrlimit(limit_kind, (min(soft_limit, hard_limit), hard_limit))
    except (OSError, ValueError):
        pass


def append_output(output, data):
    remaining = MAX_OUTPUT_BYTES - len(output)
    if remaining > 0:
        output.extend(data[:remaining])


def kill_process_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        proc.kill()


def run_command(cmd):
    output = bytearray()
    timed_out = False
    proc = subprocess.Popen(
        [*BASH, PROLOGUE + cmd],
        env=build_child_env(),
        cwd="/app",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=set_child_limits,
        start_new_session=True,
    )

    output_fd = proc.stdout.fileno()
    os.set_blocking(output_fd, False)
    deadline = time.monotonic() + TIMEOUT_SECONDS

    try:
        while True:
            now = time.monotonic()
            if now >= deadline and proc.poll() is None:
                timed_out = True
                kill_process_group(proc)
                break

            timeout = max(0, deadline - now)
            if proc.poll() is not None:
                timeout = 0

            readable, _, _ = select.select([output_fd], [], [], timeout)
            if readable:
                try:
                    chunk = os.read(output_fd, READ_CHUNK_BYTES)
                except BlockingIOError:
                    continue
                if not chunk:
                    break
                append_output(output, chunk)
            elif proc.poll() is not None:
                break

        while True:
            try:
                chunk = os.read(output_fd, READ_CHUNK_BYTES)
            except BlockingIOError:
                break
            except OSError:
                break
            if not chunk:
                break
            append_output(output, chunk)
    finally:
        if proc.poll() is None:
            kill_process_group(proc)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()

    if timed_out:
        timeout_message = b"\n[runtime] timed out\n"
        output = output[: MAX_OUTPUT_BYTES - len(timeout_message)]
        output.extend(timeout_message)

    sys.stdout.buffer.write(output[:MAX_OUTPUT_BYTES])
    sys.stdout.buffer.flush()


def main():
    print(BANNER)
    try:
        cmd = input("> ")
    except EOFError:
        return

    if len(cmd.encode("utf-8", "surrogatepass")) > MAX_COMMAND_BYTES:
        print("[policy] denied: command is too long")
        return

    denied = policy_check(cmd)
    if denied is not None:
        print(f'[policy] denied: "{denied}" is not allowed')
        return

    run_command(cmd)


if __name__ == "__main__":
    main()
