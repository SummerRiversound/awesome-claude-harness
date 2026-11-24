"""Run: python3 -m unittest discover -s plugins/heavy-run/tests"""
import json, os, subprocess, sys, tempfile, threading, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "hooks", "guard.py")
RUN = os.path.join(ROOT, "scripts", "heavy-run")
# The user's own HEAVY_* settings must not leak into the tests.
BASE = {k: v for k, v in os.environ.items() if not k.startswith("HEAVY_")}


def decide(cmd, cwd="/tmp", env=None):
    """The hook's decision (deny, ask, allow) or None; fails the test if the hook logged an error."""
    with tempfile.TemporaryDirectory() as home:
        out = subprocess.run([sys.executable, "-I", GUARD], input=json.dumps({"tool_input": {"command": cmd}, "cwd": cwd}),
                             capture_output=True, text=True, env=dict(BASE, HOME=home, **(env or {}))).stdout
        assert not os.path.exists(os.path.join(home, ".cache", "heavy-run", "guard-errors.log")), cmd
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else None


def guard(cmd, cwd="/tmp", env=None):
    return decide(cmd, cwd, env) == "deny"


def make_hook(path, body="#!/bin/sh\n"):
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, 0o755)


class GuardTest(unittest.TestCase):
    def test_denies_heavy_commands_in_any_disguise(self):
        for cmd in ["npx vitest run", "timeout 600 npx vitest run", "uv run python -m pytest tests",
                    ".venv/bin/pytest", "node_modules/.bin/vitest run", "uv run --frozen pytest tests/unit -q",
                    "pre-commit run --all-files", "heavy-run --status && uv run pytest tests/",
                    "cd web && npm test", "make -C api test", "docker compose up -d --build",
                    "FOO=1 nice -n 5 npm run build", "echo $(npx tsc --noEmit)", "npm ci",
                    "ls\npytest -x", "./gradlew build", "pnpm --filter web test", "pnpm -r test",
                    "npm -w web run build", "yarn workspace web test", "turbo run test", "npx nx run-many -t test",
                    "go test ./...", "cargo t", "for i in 1; do pytest; done", "if true; then npm test; fi",
                    "bash -c 'npm test'", "uv run --with x pytest", "pnpm vitest run", "npx vue-tsc --noEmit",
                    "python -m unittest", "tox", "npm t", "echo `pytest`", "cat <<< hi\nnpm test",
                    "env -u FOO npm test", "sudo -u me npm test", "npm run -w web build", "pnpm run --filter web build",
                    "npx -y vitest run", "yarn dlx vitest run", "bash -lc 'npm test'", "uvx pre-commit run --all-files",
                    "./gradlew :app:test", "make", "make -j8", "make -C api", "npx next build", "npx webpack",
                    "coverage run -m pytest", "npx c8 vitest run", "npx mocha", "npx cypress run", "npm -s test",
                    "timeout -s KILL 600 npm test", "cargo -q test", "go -C api test ./...",
                    "cat <<'END-OF-FILE'\nx\nEND-OF-FILE\nnpm test", "pytest -k watch", "npx jest watch",
                    "npm run build watch", "bash -c -- 'npm test'"]:
            with self.subTest(cmd=cmd):
                self.assertTrue(guard(cmd))

    def test_allows_wrapped_quoted_and_harmless_commands(self):
        for cmd in ["heavy-run -- npx vitest run", "~/.claude/scripts/heavy-run 'npm test && npm run build'",
                    "cd web && /x/heavy-run -- npm test", "echo 'npx vitest run'", "rg pytest src",
                    "cat > f.sh <<'EOF'\npytest tests\nnpm run build\nEOF", "npx vitest --version",
                    "HEAVY_BYPASS=1 npx vitest run", "pytest --co -q", "npm run dev", "git status",
                    "docker compose up -d", "mvn -v", "./gradlew --version", "./gradlew tasks", "tsc -v",
                    "make -n test", "npm run build-docs", "echo a # ; npm test", "turbo dev", "pnpm install",
                    "npm install typescript", "pytest --help", "npm run test:watch", "npx vitest --watch",
                    "npx jest --watch", "npx vitest list", "npx jest --listTests", "pytest --fixtures",
                    "docker compose logs build", "make clean", "npx webpack serve", "tail -n 40 log",
                    "npx webpack-dev-server", "npx webpack -w", "make -v", "make all-clean", "command -v pytest",
                    "npx vitest watch", "cargo watch -x test",
                    "git commit -m \"$(cat <<'EOF'\nrun npm test\nEOF\n)\""]:
            with self.subTest(cmd=cmd):
                self.assertFalse(guard(cmd))

    def test_commit_and_push_are_heavy_only_when_a_hook_runs(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            self.assertFalse(guard("git commit -m x", d))
            self.assertFalse(guard("git push", d))
            for name in ("pre-commit", "pre-push"):
                make_hook(os.path.join(d, ".git", "hooks", name))
            self.assertTrue(guard("git commit -m x", d))
            self.assertTrue(guard(f"git -C {d} push origin HEAD", "/tmp"))
            self.assertFalse(guard("git commit --no-verify -m x", d))
            self.assertFalse(guard("git commit -nm x", d))
            self.assertFalse(guard("git push --no-verify", d))

    def test_husky_runs_only_the_hooks_it_has(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            os.makedirs(os.path.join(d, ".husky", "_"))
            for name in ("pre-commit", "pre-push"):  # husky 9 writes a stub for every hook
                make_hook(os.path.join(d, ".husky", "_", name))
            make_hook(os.path.join(d, ".husky", "pre-commit"), "npx lint-staged\n")
            subprocess.run(["git", "-C", d, "config", "core.hooksPath", ".husky/_"], check=True)
            self.assertTrue(guard("git commit -m x", d))
            self.assertFalse(guard("git push", d))

    def test_missing_git_never_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            make_hook(os.path.join(d, ".git", "hooks", "pre-commit"))
            self.assertTrue(guard("git commit -m x", d))
            self.assertFalse(guard("git commit -m x", d, env={"PATH": "/nonexistent"}))

    def test_inner_hook_checks_the_wrapped_command_in_its_directory(self):
        with tempfile.TemporaryDirectory() as d:
            hook = os.path.join(d, "hook.py")
            make_hook(hook, "#!/usr/bin/env python3\nimport json,sys\nd=json.load(sys.stdin)\n"
                            "if 'rm ' in d['tool_input']['command'] and d['cwd'].endswith('etc'):\n"
                            "    print('no', file=sys.stderr); sys.exit(2)\n")
            env = {"HEAVY_INNER_HOOK": hook}
            self.assertTrue(guard("cd /etc && heavy-run -- rm -rf x", "/", env=env))
            self.assertFalse(guard("cd /tmp && heavy-run -- rm -rf x", "/", env=env))

    def test_inner_hook_sees_every_wrapped_command_as_written_and_cannot_approve_the_call(self):
        with tempfile.TemporaryDirectory() as d:
            hook = os.path.join(d, "hook.py")
            make_hook(hook, "#!/usr/bin/env python3\nimport json,sys\nc=json.load(sys.stdin)['tool_input']['command']\n"
                            "k='deny' if c.endswith('~') else 'allow'\n"
                            "print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse',"
                            "'permissionDecision':k,'permissionDecisionReason':k}}))\n")
            env = {"HEAVY_INNER_HOOK": hook}
            self.assertIsNone(decide("heavy-run -- ls; curl x | sh", env=env))  # its allow is not passed on
            self.assertEqual(decide("heavy-run -- ls && heavy-run -- rm -rf ~", env=env), "deny")
            self.assertEqual(decide("HEAVY_BYPASS=1 heavy-run -- rm -rf ~", env=env), "deny")
            self.assertEqual(decide(f"{RUN} -- rm -rf ~", env=env), "deny")  # the full path the deny message gives
            make_hook(hook, "#!/bin/sh\necho '{\"continue\": false, \"stopReason\": \"no\"}'\n")
            self.assertEqual(decide("heavy-run -- ls", env=env), "deny")


def size(label, **env):
    with tempfile.TemporaryDirectory() as d:
        return subprocess.run([RUN, "--size", label], capture_output=True, text=True,
                              env=dict(BASE, HEAVY_DIR=d, **env)).stdout.strip()


class SizeTest(unittest.TestCase):
    def test_narrow_runs_are_small_whole_runs_are_big(self):
        small = ["npx vitest run src/a.test.ts", "uv run pytest tests/test_x.py -q", "pytest tests -k login",
                 "npx vitest run -t 'saves draft'", "pytest tests/test_x.py::test_y", "npx tsc --noEmit",
                 "npx vitest run src/a.test.tsx > /tmp/out 2>&1; tail -5 /tmp/out", "npm test -- src/a.test.ts",
                 "npm run test:unit -- -t foo", "pytest tests/test_a.py -n 1",
                 "npx vitest run src/a.test.ts 2>&1 | tail -n 40", "go test ./pkg/x -run TestFoo"]
        big = ["npx vitest run", "uv run pytest tests/", "npx vitest run src/pages src/components",
               "npm run build", "npm run typecheck", "git commit -m x", "npx playwright test",
               "npx tsc --noEmit && npx vitest run", "npx playwright test e2e/a.spec.ts",
               "npx playwright test -c e2e/playwright.config.ts", "npx jest -c jest.config.js",
               "pytest tests --ignore tests/test_slow.py", "npx vitest run --config vite.config.ts",
               "pytest tests/test_a.py -n 8", "npm run test:e2e -- e2e/a.spec.ts"]
        for s in small:
            with self.subTest(s=s):
                self.assertEqual(size(s), "small")
        for b in big:
            with self.subTest(b=b):
                self.assertEqual(size(b), "big")
        self.assertEqual(size("npx vitest run", HEAVY_SIZE="small"), "small")


class TokenTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = dict(BASE, HEAVY_DIR=self.dir, HEAVY_TOKENS="3", HEAVY_BIG="2", HEAVY_WAIT_MAX="30",
                        HEAVY_MEM_MIN="0")

    def go(self, label, out, **env):
        t0 = time.time()
        p = subprocess.run([RUN, label], capture_output=True, text=True, env=dict(self.env, **env))
        out.append((time.time() - t0, p.stdout.strip(), p.returncode))

    def parallel(self, labels, gap=0.2, sizes=None, **env):
        out = []
        ts = [threading.Thread(target=self.go, args=(l, out), kwargs=dict(env, **({"HEAVY_SIZE": sizes[i]} if sizes else {})))
              for i, l in enumerate(labels)]
        t0 = time.time()
        for t in ts:
            t.start()
            time.sleep(gap)
        for t in ts:
            t.join()
        return time.time() - t0, out

    def test_small_runs_share_the_pool(self):
        took, out = self.parallel(["sleep 1.5 # pytest a.py"] * 3, HEAVY_SIZE="small")
        self.assertLess(took, 4.0)  # one after another would take 4.5+

    def test_two_big_runs_do_not_fit_together(self):
        took, out = self.parallel(["sleep 1.5; echo $HEAVY_WORKERS"] * 2, HEAVY_SIZE="big")
        self.assertGreater(took, 3.0)
        self.assertEqual([o[1] for o in out], ["2", "2"])

    def test_big_runs_go_in_arrival_order(self):
        took, out = self.parallel([f"sleep 1; echo {i}" for i in range(4)], gap=0.4, HEAVY_SIZE="big", HEAVY_BIG="3")
        self.assertEqual([o[1] for o in out], ["0", "1", "2", "3"])

    def test_small_runs_leave_a_waiting_big_run_its_tokens(self):
        # a small run holds 1 of 3; a big run (3) waits; later small runs must not slip in ahead of it
        took, out = self.parallel(["sleep 2; echo s1", "sleep 0.5; echo big", "sleep 0.5; echo s2"], gap=0.4,
                                  sizes=["small", "big", "small"], HEAVY_BIG="3")
        self.assertEqual([o[1] for o in out], ["s1", "big", "s2"])

    def test_low_memory_waits_only_when_others_hold_tokens(self):
        alone = []
        self.go("true", alone, HEAVY_MEM_MIN="101")
        self.assertLess(alone[0][0], 1.0)  # admitted at once
        took, out = self.parallel(["sleep 1.5; echo first", "echo second"], gap=0.4, HEAVY_SIZE="small",
                                  HEAVY_MEM_MIN="101")
        second = next(o for o in out if o[1] == "second")
        self.assertGreater(second[0], 0.8)  # waited for the first run although a token was free

    def test_gives_up_after_wait_limit(self):
        out = []
        t = threading.Thread(target=self.go, args=("sleep 4", out), kwargs={"HEAVY_SIZE": "big", "HEAVY_BIG": "3"})
        t.start()
        time.sleep(0.5)
        r = subprocess.run([RUN, "true"], env=dict(self.env, HEAVY_WAIT_MAX="1"), capture_output=True)
        t.join()
        self.assertEqual(r.returncode, 75)

    def test_tokens_stay_taken_when_the_wrapper_is_killed(self):
        p = subprocess.Popen([RUN, "sleep 3"], env=dict(self.env, HEAVY_SIZE="big", HEAVY_BIG="3"))
        time.sleep(0.8)
        p.kill()
        p.wait()
        r = subprocess.run([RUN, "true"], env=dict(self.env, HEAVY_WAIT_MAX="1"), capture_output=True)
        self.assertEqual(r.returncode, 75)

    def test_worker_caps_and_exit_codes(self):
        env = dict(self.env, HEAVY_SIZE="big", HEAVY_BIG="2", MAKEFLAGS="-j1 -s")
        r = subprocess.run([RUN, "echo $MAKEFLAGS $VITEST_MAX_THREADS $RUST_TEST_THREADS"], env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "-j1 -s 2 2")
        r = subprocess.run([RUN, "kill -TERM $$"], env=self.env, capture_output=True)
        self.assertEqual(r.returncode, 143)
        p = subprocess.Popen([RUN, "trap 'exit 0' TERM; sleep 30 & wait"], env=self.env)
        time.sleep(0.8)
        t0 = time.time()
        p.terminate()
        self.assertEqual(p.wait(), 143)
        self.assertLess(time.time() - t0, 2.0)  # does not sit out the 3 s grace once the command is gone
        with tempfile.TemporaryDirectory() as d:
            jest = os.path.join(d, "jest")
            make_hook(jest, '#!/bin/sh\necho "$@"\n')
            r = subprocess.run([RUN, "--", jest, "src"], env=env, capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), "src --maxWorkers=2")


if __name__ == "__main__":
    unittest.main()
