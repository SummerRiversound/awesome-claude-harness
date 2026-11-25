"""PreToolUse(Bash): tests, type checks, builds and hook-running commits must go through heavy-run.

Splits the command into segments the way the shell does (quotes, # comments and heredoc bodies
are not commands), strips env assignments, wrappers such as timeout or nice and shell keywords,
looks inside bash -c / sh -c / eval strings, and denies a segment that starts a heavy tool. A
segment that is itself a heavy-run call is allowed. A guard error never blocks: it is logged to
~/.cache/heavy-run/guard-errors.log and the call goes through.
"""
import json, os, re, shlex, sys, time, traceback

STARTED = time.time()
HERE = os.path.dirname(os.path.realpath(__file__))
UV = (r"uv run(?: (?:--with|--with-requirements|--python|-p|--project|--directory|--package|--extra|--group|"
      r"--env-file)[ =]\S+| --?[\w-]+)*")
NPX = r"(?:npx|bunx|bun x|npm exec|pnpm(?: exec| dlx)?|yarn(?: run| dlx)?)(?: (?:-y|--yes|-q|--quiet|(?:-p|--package)[ =]\S+))*"
WRAP = rf"(?:{NPX}|{UV}|uvx|poetry run|python3? -m|coverage run(?: -m)?|c8|nyc)"
# Workspace options that may sit between the package manager and the script name.
PM_OPTS = (r"(?:(?:--filter|-F|-w|--workspace|--prefix|-C|--dir)[ =]\S+ |"
           r"(?:-r|--recursive|--parallel|--if-present|-ws|--workspaces|-s|--silent|-q|--quiet) )*")
SCRIPTS = r"(?:test|type-?check|tsc|build|lint|e2e|check|verify|validate)(?::\S+)?(?:\s|$)"
HEAVY = [re.compile(r"\A" + p) for p in (
    rf"(?:{WRAP} )*(?:vitest|jest)\b",
    rf"(?:npm|pnpm|bun) {PM_OPTS}(?:(?:run|run-script) {PM_OPTS})?(?:t(?:\s|$)|{SCRIPTS})",
    rf"yarn (?:workspace \S+ |workspaces foreach (?:-\S+ )*)?{PM_OPTS}(?:run {PM_OPTS})?{SCRIPTS}",
    r"(?:npm|pnpm) ci\b",
    rf"(?:{WRAP} )*(?:vue-)?tsc\b",
    rf"(?:{WRAP} )*pytest\b",
    rf"(?:{WRAP} )*(?:pyright|mypy|tox|nox|unittest)\b",
    r"cargo (?:\+\S+ )?(?:-\S+ )*(?:build|b|test|t|check|c|clippy|nextest)\b",
    r"go (?:-C \S+ )?(?:test|build|vet)\b",
    r"(?:dotnet|swift) (?:test|build)\b",
    r"deno test\b",
    rf"(?:{WRAP} )*turbo (?:run )?(?:\S+ )*?(?:test|build|lint|check|type-?check|e2e)\b",
    rf"(?:{WRAP} )*nx (?:(?:test|build|lint|e2e)\b|(?:run-many|affected)\b.*\b(?:test|build|lint|e2e)\b)",
    rf"(?:{WRAP} )*playwright test\b",
    rf"(?:{WRAP} )*(?:vite|next|nuxt|nuxi|astro|svelte-kit|remix) build\b",
    rf"(?:{WRAP} )*webpack(?![-\w])(?! (?:serve|watch)\b)",
    rf"(?:{WRAP} )*(?:mocha\b|cypress run\b)",
    r"(?:gradlew|gradle|mvnw|mvn) (?:\S+ )*?(?:\S*:)?(?:build|test|check|assemble|install|package|verify|"
    r"compile\S*|integrationTest)\b",
    r"docker (?:buildx )?build\b|docker compose (?:--?\S+ \S+ )*(?:build\b|up\b.* --build\b)",
    rf"(?:{WRAP} )*pre-commit run\b",
    r"make (?:\S+ )*?(?:test|check|build|lint|all)(?=\s|$)",
    r"make(?: (?:-[Cfj] ?\S+|-\S+|\w+=\S*))*$",  # the default target is usually the build
)]
# Asking a tool for its version, help, config or a dry run is not a run.
LIGHT = {"--version", "--help", "-h", "--dry-run", "--init", "--showConfig", "--collect-only", "--co", "--listTests",
         "--list", "--fixtures", "--markers", "--watch", "--watchAll"}
LIGHT_BY_TOOL = {"mvn": {"-v", "-V"}, "mvnw": {"-v", "-V"}, "gradle": {"-v"}, "gradlew": {"-v"}, "tsc": {"-v"},
                 "make": {"-n", "--just-print", "-v"}, "webpack": {"-w"}}
PREFIX = {"timeout", "gtimeout", "time", "env", "nice", "command", "exec", "nohup", "caffeinate", "sudo", "stdbuf",
          "do", "then", "else", "elif", "if", "while", "until", "{", "!"}
TAKES_VALUE = {"env": {"-u", "-C", "-S"}, "sudo": {"-u", "-g", "-C"}, "nice": {"-n"},
               "timeout": {"-s", "-k", "--signal", "--kill-after"}, "gtimeout": {"-s", "-k", "--signal", "--kill-after"}}
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
        tags = re.findall(r"(?<![<\w])<<(?!<)-?\s*['\"]?([^\s'\"<>;&|()]+)['\"]?", lines[i])
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
        elif os.path.basename(w[0]) == "command" and w[1:2] in (["-v"], ["-V"]):
            return [], bypass  # a lookup, not a run
        elif os.path.basename(w[0]) in PREFIX:
            name, w = os.path.basename(w[0]), w[1:]
            while w and (w[0].startswith("-") or (name in ("timeout", "gtimeout") and re.fullmatch(r"[\d.]+[smhd]?", w[0]))):
                w = w[2:] if w[0] in TAKES_VALUE.get(name, ()) else w[1:]
        else:
            break
    return w, bypass


def git_paths(root, name):
    """(repo top, common git dir, path git runs the hook from), or None when not a repo or git fails."""
    import subprocess
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


def wrapped(seg):
    """The command text a heavy-run segment runs, as the shell will see it (no requoting)."""
    rest = re.split(r"heavy-run(?=\s|$)", seg, maxsplit=1)[1].strip()  # not the plugins/heavy-run/ directory
    rest = re.sub(r"\A--(?:\s+|\Z)", "", rest)
    if not rest or rest.startswith("--"):
        return None
    w = words_of(rest)
    return w[0] if len(w) == 1 else rest


def is_light(w):
    names = [os.path.basename(a) for a in w]
    return (any(a in LIGHT or a.endswith(":watch") for a in w[1:])
            or any(n in LIGHT_BY_TOOL and LIGHT_BY_TOOL[n] & set(w[i + 1:]) for i, n in enumerate(names))
            or any(n in ("vitest", "cargo") and w[i + 1:i + 2] in (["list"], ["dev"], ["watch"])
                   for i, n in enumerate(names)))


def script_file(w, cwd):
    """The file a shell will read and run for these words (bash f, sh -e f, ./f with a shell shebang), or None.
    `source f` is left out: it mostly loads rc and env files whose function bodies never run."""
    head, path = os.path.basename(w[0]), None
    if head in SHELLS:
        i = 1
        while i < len(w) and w[i][:1] in "-+":
            if w[i] == "-s":
                return None  # reads the script from stdin
            i += 2 if w[i] in ("-o", "+o") else 1
        path = w[i] if i < len(w) else None
    elif "/" in w[0]:
        path = w[0]
    if not path:
        return None
    path = os.path.join(cwd, os.path.expanduser(path))
    if not os.path.isfile(path):
        return None
    if head not in SHELLS:
        with open(path, errors="replace") as f:
            if not re.match(r"#!.*\b(?:ba|z|da)?sh\b", f.readline(256)):
                return None
    return path


def check(cmd, cwd, depth=0):
    """Returns (heavy segment or None, list of (command wrapped in heavy-run, its cwd))."""
    inner = []
    for seg in segments(strip_heredocs(cmd)):
        w, bypass = strip_prefix(words_of(seg))
        if not w:
            continue
        head = os.path.basename(w[0])
        if head == "cd" and len(w) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(w[1]))
            continue
        if head == "heavy-run":
            body = wrapped(seg)
            if body:
                inner.append((body, cwd))
            continue
        flag = next((i for i, a in enumerate(w[1:-1], 1) if re.fullmatch(r"-[a-z]*c[a-z]*", a)), None)
        if depth < 3 and ((head in SHELLS and flag) or head == "eval"):
            if head in SHELLS and w[flag + 1] == "--":
                flag += 1
            if head in SHELLS and flag + 1 >= len(w):
                continue
            body = w[flag + 1] if head in SHELLS else " ".join(w[1:])
            found, more = check(body, cwd, depth + 1)
            inner += more
            if found and not bypass:
                return seg, inner
            continue
        if bypass:
            continue
        script = script_file(w, cwd) if depth < 3 else None
        if script:
            with open(script, errors="replace") as f:
                found, more = check(f.read(256 * 1024), cwd, depth + 1)  # the script runs in the caller's cwd
            inner += more
            if found:
                return seg, inner
        if head == "git":
            if git_heavy(w, cwd):
                return seg, inner
            continue
        if is_light(w):
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
        f"A script file that runs them goes through it whole: `{run} bash <file> <args>`. "
        "A whole suite, build or hook-running commit takes 3 tokens and 3 workers; a run narrowed to files or a "
        "name filter (-t, -k, a test file path, file::test) takes 1, so narrow it when that is all you need. "
        "It may wait for tokens before it starts, so give the Bash call timeout 7200000; for a whole suite or "
        "build, also set run_in_background and keep working until it reports back. "
        "Never wrap dev servers or watch mode, which never finish and would hold tokens; anything the wrapped "
        "command starts in the background is stopped when it ends. "
        f"Do not split the work to dodge the wait. `{run} --status` shows who holds the tokens.")
    decision("deny", reason)


def decision(kind, reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": kind,
                                             "permissionDecisionReason": reason}}))


def run_inner_hook(hook, data, inner):
    """Other hooks only see the wrapper; let one of them check each wrapped command too.
    Only its deny or ask is passed on: an allow for one wrapped command must not approve the whole call."""
    import subprocess
    argv = [hook] if os.access(hook, os.X_OK) else ["bash", hook]
    deadline, ask = STARTED + 8, None  # stay inside the 10 s hook timeout in hooks.json
    for cmd, cwd in inner:
        left = deadline - time.time()
        if left <= 0:
            break
        try:
            r = subprocess.run(argv, input=json.dumps(dict(data, cwd=cwd, tool_input={"command": cmd})),
                               capture_output=True, text=True, timeout=min(4, left))
        except (subprocess.TimeoutExpired, OSError):
            continue
        if r.returncode == 2:  # the documented blocking exit: stderr is the reason
            return decision("deny", r.stderr.strip() or "blocked")
        try:
            out = json.loads(r.stdout or "null") or {}
            spec = out.get("hookSpecificOutput") or {}
            kind = (spec.get("permissionDecision") or {"block": "deny"}.get(out.get("decision"))
                    or ("deny" if out.get("continue") is False else None))
            why = spec.get("permissionDecisionReason") or out.get("reason") or out.get("stopReason") or "blocked"
        except (ValueError, AttributeError):
            continue
        if kind == "deny":
            return decision("deny", why)
        if kind == "ask" and ask is None:
            ask = why
    if ask is not None:
        decision("ask", ask)


def main():
    data = json.load(sys.stdin)
    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd or not isinstance(cmd, str):
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
