"""PreToolUse(Bash): tests, type checks, builds and hook-running commits must go through heavy-run.

Splits the command into segments the way the shell does (quotes, # comments and heredoc bodies
are not commands), strips env assignments, wrappers such as timeout or nice and shell keywords,
looks inside bash -c / sh -c / eval strings, and denies a segment that starts a heavy tool. A
segment that is itself a heavy-run call is allowed. A guard error never blocks: it is logged to
~/.cache/heavy-run/guard-errors.log and the call goes through.
"""
import json, os, re, shlex, subprocess, sys, traceback

HERE = os.path.dirname(os.path.realpath(__file__))
UV = (r"uv run(?: (?:--with|--with-requirements|--python|-p|--project|--directory|--package|--extra|--group|"
      r"--env-file)[ =]\S+| --?[\w-]+)*")
WRAP = rf"(?:npx|bunx|pnpm(?: exec| dlx)?|npm exec|yarn(?: run)?|{UV}|uvx|poetry run|python3? -m|bun x)"
# Workspace options that may sit between the package manager and the script name.
PM_OPTS = (r"(?:(?:--filter|-F|-w|--workspace|--prefix|-C|--dir)[ =]\S+ |"
           r"(?:-r|--recursive|--parallel|--if-present|-ws|--workspaces) )*")
SCRIPTS = r"(?:test|type-?check|tsc|build|lint|e2e|check|verify|validate)(?::\S+)?(?:\s|$)"
HEAVY = [re.compile(r"\A" + p) for p in (
    rf"(?:{WRAP} )*(?:vitest|jest)\b",
    rf"(?:npm|pnpm|bun) {PM_OPTS}(?:run )?(?:t(?:\s|$)|{SCRIPTS})",
    rf"yarn (?:workspace \S+ |workspaces foreach (?:-\S+ )*)?{PM_OPTS}(?:run )?{SCRIPTS}",
    r"(?:npm|pnpm) ci\b",
    rf"(?:{WRAP} )*(?:vue-)?tsc\b",
    rf"(?:{WRAP} )*pytest\b",
    rf"(?:{WRAP} )*(?:pyright|mypy|tox|nox|unittest)\b",
    r"cargo (?:\+\S+ )?(?:build|b|test|t|check|c|clippy|nextest)\b",
    r"go (?:test|build|vet)\b",
    r"(?:dotnet|swift) (?:test|build)\b",
    r"deno test\b",
    rf"(?:{WRAP} )*turbo (?:run )?(?:\S+ )*?(?:test|build|lint|check|type-?check|e2e)\b",
    rf"(?:{WRAP} )*nx (?:(?:test|build|lint|e2e)\b|(?:run-many|affected)\b.*\b(?:test|build|lint|e2e)\b)",
    rf"(?:{WRAP} )*playwright test\b",
    rf"(?:{WRAP} )*vite build\b",
    r"(?:gradlew|gradle|mvnw|mvn) (?:\S+ )*?(?:build|test|check|assemble|install|package|verify|compile\S*|"
    r"integrationTest)\b",
    r"docker (?:buildx )?build\b|docker compose (?:\S+ )*?(?:build\b|up\b.* --build\b)",
    r"pre-commit run\b",
    r"make (?:\S+ )*?(?:test|check|build|lint)\b",
)]
# Asking a tool for its version, help, config or a dry run is not a run.
LIGHT = {"--version", "--help", "-h", "--dry-run", "--init", "--showConfig", "--collect-only", "--co"}
LIGHT_BY_TOOL = {"mvn": {"-v", "-V"}, "mvnw": {"-v", "-V"}, "gradle": {"-v"}, "gradlew": {"-v"}, "tsc": {"-v"},
                 "make": {"-n", "--just-print"}}
PREFIX = {"timeout", "gtimeout", "time", "env", "nice", "command", "exec", "nohup", "caffeinate", "sudo", "stdbuf",
          "do", "then", "else", "elif", "if", "while", "until", "{", "!"}
TAKES_VALUE = {"env": {"-u", "-C", "-S"}, "sudo": {"-u", "-g", "-C"}, "nice": {"-n"}}
SHELLS = {"bash", "sh", "zsh", "dash"}
ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def heavy_run_path():
    for p in (os.environ.get("HEAVY_RUN", ""), os.path.join(HERE, "..", "scripts", "heavy-run"),
              os.path.expanduser("~/.claude/scripts/heavy-run")):
        if p and os.path.exists(p):
            return os.path.realpath(p)
    return "heavy-run"


def strip_heredocs(cmd):
    out, lines, i = [], cmd.split("\n"), 0
    while i < len(lines):
        out.append(lines[i])
        # not a here-string (<<<) and not a shift inside $(( ))
        tags = re.findall(r"(?<![<\w])<<(?!<)-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", lines[i])
        i += 1
        for tag in tags:
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            i += 1
    return "\n".join(out)


def segments(cmd):
    """Split on ; & && || | ( ) ` and newlines outside quotes, dropping # comments."""
    segs, cur, q, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur.append(c)
            if c == "\\" and q == '"' and i + 1 < len(cmd):
                cur.append(cmd[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c == "\\" and i + 1 < len(cmd):
            cur.append(cmd[i:i + 2])
            i += 1
        elif c == "#" and (not cur or cur[-1] in " \t"):
            while i + 1 < len(cmd) and cmd[i + 1] != "\n":
                i += 1
        elif c in "'\"":
            q = c
            cur.append(c)
        elif c in ";&|()`\n" and not (c == "&" and cur and cur[-1] in "<>"):
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return [s.strip() for s in segs if s.strip()]


def words_of(seg):
    try:
        return shlex.split(seg)
    except ValueError:
        return seg.split()


def strip_prefix(w):
    """Drop env assignments, wrappers (timeout 600, nice -n 5, env -u X) and shell keywords."""
    bypass = False
    while w:
        if ASSIGN.match(w[0]):
            bypass |= w[0] == "HEAVY_BYPASS=1"
            w = w[1:]
        elif os.path.basename(w[0]) in PREFIX:
            name, w = os.path.basename(w[0]), w[1:]
            while w and (w[0].startswith("-") or (name in ("timeout", "gtimeout") and re.fullmatch(r"[\d.]+[smhd]?", w[0]))):
                w = w[2:] if w[0] in TAKES_VALUE.get(name, ()) else w[1:]
        else:
            break
    return w, bypass


def git_paths(root, name):
    """(repo top, common git dir, path git runs the hook from), or None when not a repo or git fails."""
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--path-format=absolute", "--show-toplevel",
                              "--git-common-dir", "--git-path", f"hooks/{name}"],
                             capture_output=True, text=True, timeout=3)
    except Exception:
        return None
    lines = out.stdout.split("\n")
    return tuple(lines[:3]) if out.returncode == 0 and len(lines) >= 3 else None


def executable(p):
    return os.path.isfile(p) and os.access(p, os.X_OK)


def hook_installed(root, name):
    """Whether the repo's own hook runs. A global hooks dispatcher outside the repo does not count by
    itself, but the repo's .git/hooks still does, since such dispatchers usually call it."""
    paths = git_paths(root, name)
    if not paths:
        return False  # cannot tell: let the call through rather than block on a guard error
    top, common, runs = paths
    if runs.startswith(top + os.sep):
        if f"{os.sep}.husky{os.sep}_{os.sep}" in runs:  # husky 9 stubs exist for every hook
            return os.path.isfile(os.path.join(top, ".husky", name))
        return executable(runs)
    return executable(runs) if runs.startswith(common + os.sep) else executable(os.path.join(common, "hooks", name))


def git_heavy(w, cwd):
    i = 1
    while i < len(w) and w[i].startswith("-"):
        if w[i] in ("-C", "-c") and i + 1 < len(w):
            if w[i] == "-C":
                cwd = os.path.join(cwd, os.path.expanduser(w[i + 1]))
            elif re.match(r"core\.hooksPath=/dev/null$", w[i + 1]):
                return False
            i += 1
        i += 1
    if i >= len(w) or w[i] not in ("commit", "push"):
        return False
    sub, rest = w[i], w[i + 1:]
    if "--no-verify" in rest or (sub == "commit" and any(re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a) for a in rest)):
        return False
    return hook_installed(cwd, "pre-commit" if sub == "commit" else "pre-push")


def check(cmd, cwd, depth=0):
    """Returns (heavy segment or None, list of (command wrapped in heavy-run, its cwd))."""
    inner = []
    for seg in segments(strip_heredocs(cmd)):
        w, bypass = strip_prefix(words_of(seg))
        if bypass or not w:
            continue
        head = os.path.basename(w[0])
        if head == "cd" and len(w) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(w[1]))
            continue
        if head == "heavy-run":
            rest = w[2:] if len(w) > 1 and w[1] == "--" else w[1:]
            if rest and not rest[0].startswith("--"):
                inner.append((rest[0] if len(rest) == 1 else shlex.join(rest), cwd))
            continue
        if depth < 3 and ((head in SHELLS and "-c" in w[1:-1]) or head == "eval"):
            body = w[w.index("-c") + 1] if head in SHELLS else " ".join(w[1:])
            found, more = check(body, cwd, depth + 1)
            inner += more
            if found:
                return seg, inner
            continue
        if head == "git":
            if git_heavy(w, cwd):
                return seg, inner
            continue
        if any(a in LIGHT or a in LIGHT_BY_TOOL.get(head, ()) for a in w[1:]):
            continue
        line = " ".join([head] + w[1:])
        if any(p.search(line) for p in HEAVY):
            return seg, inner
    return None, inner


def deny(seg):
    run = shlex.quote(heavy_run_path())
    reason = (
        f"Heavy command ({seg[:80]}). Every Claude session on this computer shares one pool of CPU tokens, "
        "so runs do not starve each other. Rerun it through the wrapper, keeping `cd` outside: "
        f"`cd <dir> && {run} -- <command and args>`, or one quoted shell string: `{run} '<cmd> && <cmd>'`. "
        "A whole suite, build or hook-running commit takes 3 tokens and 3 workers; a run narrowed to files or a "
        "name filter (-t, -k, a test file path, file::test) takes 1, so narrow it when that is all you need. "
        "It may wait for tokens before it starts, so give the Bash call timeout 7200000; for a whole suite or "
        "build, also set run_in_background and keep working until it reports back. "
        "Never wrap dev servers or watch mode, which never finish and would hold tokens; anything the wrapped "
        "command starts in the background is stopped when it ends. "
        f"Do not split the work to dodge the wait. `{run} --status` shows who holds the tokens.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def run_inner_hook(hook, data, inner):
    """Other hooks only see the wrapper; let one of them check each wrapped command too."""
    argv = [hook] if os.access(hook, os.X_OK) else ["bash", hook]
    for cmd, cwd in inner:
        try:
            r = subprocess.run(argv, input=json.dumps(dict(data, cwd=cwd, tool_input={"command": cmd})),
                               capture_output=True, text=True, timeout=4)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode == 2:  # the documented blocking exit: stderr is the reason
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                     "permissionDecisionReason": r.stderr.strip() or "blocked"}}))
            return
        if r.stdout.strip():
            print(r.stdout)
            return


def main():
    data = json.load(sys.stdin)
    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        return
    seg, inner = check(cmd, data.get("cwd") or os.getcwd())
    if seg:
        deny(seg)
        return
    hook = os.path.expanduser(os.environ.get("HEAVY_INNER_HOOK", ""))
    if inner and hook and os.path.isfile(hook):
        run_inner_hook(hook, data, inner)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            d = os.path.expanduser("~/.cache/heavy-run")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "guard-errors.log"), "a") as f:
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass
