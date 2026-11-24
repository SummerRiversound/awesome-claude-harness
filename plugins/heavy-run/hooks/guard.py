"""PreToolUse(Bash): tests, type checks, builds and hook-running commits must go through heavy-run.

Splits the command into segments the way the shell does (quotes and heredoc bodies are not
commands), strips env assignments and wrappers such as timeout or nice, and denies a segment
that starts a heavy tool. A segment that is itself a heavy-run call is allowed. A guard error
never blocks: it is logged to ~/.cache/heavy-run/guard-errors.log and the call goes through.
"""
import json, os, re, shlex, subprocess, sys, traceback

HERE = os.path.dirname(os.path.realpath(__file__))
WRAP = r"(?:npx|bunx|pnpm (?:exec|dlx)|yarn(?: run)?|uv run(?: --?\S+)*|uvx|poetry run|python3? -m|bun x)"
HEAVY = [re.compile(r"\A" + p) for p in (
    rf"(?:{WRAP} )*(?:vitest|jest)\b(?! --(?:version|help))",
    r"(?:npm|pnpm|yarn|bun) (?:run )?(?:test|type-?check|build|lint|e2e)(?::\S+)?\b",
    r"(?:npm|pnpm) ci\b",
    rf"(?:{WRAP} )*tsc\b(?! --(?:version|help))",
    rf"(?:{WRAP} )*pytest\b(?!.* --(?:co|collect-only|version|help)\b)",
    rf"(?:{WRAP} )*(?:pyright|mypy)\b(?! --version)",
    r"cargo (?:build|test|check|clippy|nextest)\b",
    rf"(?:{WRAP} )*playwright test\b",
    rf"(?:{WRAP} )*vite build\b",
    r"(?:gradlew|gradle|mvn|mvnw) ",
    r"docker (?:buildx )?build\b|docker compose (?:\S+ )*?(?:build\b|up\b.* --build\b)",
    r"pre-commit run\b",
    r"make (?:\S+ )*?(?:test|check|build|lint)\b",
)]
PREFIX = {"timeout", "gtimeout", "time", "env", "nice", "command", "exec", "nohup", "caffeinate"}
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
        tags = re.findall(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", lines[i])
        i += 1
        for tag in tags:
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            i += 1
    return "\n".join(out)


def segments(cmd):
    """Split on ; & && || | ( ) and newlines outside quotes."""
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
        elif c in "'\"":
            q = c
            cur.append(c)
        elif c in ";&|()\n" and not (c == "&" and cur and cur[-1] in "<>"):
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return [s.strip() for s in segs if s.strip()]


def words_of(seg):
    try:
        return shlex.split(seg, comments=True)
    except ValueError:
        return seg.split()


def strip_prefix(w):
    """Drop env assignments and wrappers (timeout 600, nice -n 5, env -i A=1 ...). Returns (words, bypass)."""
    bypass = False
    while w:
        if ASSIGN.match(w[0]):
            bypass |= w[0] == "HEAVY_BYPASS=1"
            w = w[1:]
        elif os.path.basename(w[0]) in PREFIX:
            name, w = os.path.basename(w[0]), w[1:]
            while w and (w[0].startswith("-") or (name in ("timeout", "gtimeout") and re.fullmatch(r"[\d.]+[smhd]?", w[0]))
                         or (name == "nice" and re.fullmatch(r"-?\d+", w[0]))):
                w = w[1:]
        else:
            break
    return w, bypass


def hook_installed(root, name):
    """The repo's own hook: .git/hooks, a hooks path inside the repo (husky), not a global dispatcher."""
    def git(*a):
        return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True, timeout=5).stdout.strip()
    try:
        top = git("rev-parse", "--show-toplevel")
        if not top:
            return False
        common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
        cands = [os.path.join(common, "hooks", name), os.path.join(top, ".husky", name)]
        p = git("rev-parse", "--path-format=absolute", "--git-path", f"hooks/{name}")
        if p.startswith(top + os.sep):
            cands.append(p)
    except Exception:
        return True  # cannot tell: treat as heavy
    return any(os.path.isfile(c) and os.access(c, os.X_OK) or c.endswith(f".husky/{name}") and os.path.isfile(c)
               for c in cands)


def git_heavy(w, cwd):
    i = 1
    while i < len(w) and w[i].startswith("-"):
        if w[i] in ("-C", "-c") and i + 1 < len(w):
            if w[i] == "-C":
                cwd = os.path.join(cwd, os.path.expanduser(w[i + 1]))
            i += 1
        i += 1
    if i >= len(w) or w[i] not in ("commit", "push"):
        return False
    sub, rest = w[i], w[i + 1:]
    if "--no-verify" in rest or (sub == "commit" and any(re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a) for a in rest)):
        return False
    return hook_installed(cwd, "pre-commit" if sub == "commit" else "pre-push")


def check(cmd, cwd):
    """Returns (heavy segment or None, list of commands wrapped in heavy-run)."""
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
                inner.append(rest[0] if len(rest) == 1 else shlex.join(rest))
            continue
        if head == "git":
            if git_heavy(w, cwd):
                return seg, inner
            continue
        line = " ".join([head] + w[1:])
        if any(p.search(line) for p in HEAVY):
            return seg, inner
    return None, inner


def deny(seg):
    run = heavy_run_path()
    reason = (
        f"Heavy command ({seg[:80]}). Every Claude session on this computer shares one pool of CPU tokens, "
        "so runs do not starve each other. Rerun it through the wrapper, keeping `cd` outside: "
        f"`cd <dir> && {run} -- <command and args>`, or one quoted shell string: `{run} '<cmd> && <cmd>'`. "
        "A whole suite, build or hook-running commit takes 3 tokens and 3 workers; a run narrowed to files or a "
        "name filter (-t, -k, a file path, file::test) takes 1, so narrow it when that is all you need. "
        "It may wait for tokens: run it in the background, or give the Bash call timeout 3600000. "
        "Never wrap dev servers or watch mode, which never finish and would hold tokens. "
        f"Do not split the work to dodge the wait. `{run} --status` shows who holds the tokens.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def main():
    data = json.load(sys.stdin)
    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        return
    seg, inner = check(cmd, data.get("cwd") or os.getcwd())
    if seg:
        deny(seg)
        return
    hook = os.environ.get("HEAVY_INNER_HOOK", "")
    if inner and hook and os.path.exists(os.path.expanduser(hook)):
        # Other hooks only see the wrapper; give one of them the wrapped commands too.
        out = subprocess.run(["bash", os.path.expanduser(hook)],
                             input=json.dumps(dict(data, tool_input={"command": "\n".join(inner)})),
                             capture_output=True, text=True, timeout=10).stdout
        if out.strip():
            print(out)


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
