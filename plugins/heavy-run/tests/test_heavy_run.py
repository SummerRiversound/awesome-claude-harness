"""Run: python3 -m unittest discover -s plugins/heavy-run/tests"""
import json, os, subprocess, sys, tempfile, threading, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "hooks", "guard.py")
RUN = os.path.join(ROOT, "scripts", "heavy-run")


def guard(cmd, cwd="/tmp", env=None):
    out = subprocess.run([sys.executable, "-I", GUARD], input=json.dumps({"tool_input": {"command": cmd}, "cwd": cwd}),
                         capture_output=True, text=True, env=dict(os.environ, **(env or {}))).stdout
    return "deny" in out


class GuardTest(unittest.TestCase):
    def test_denies_heavy_commands_in_any_disguise(self):
        for cmd in ["npx vitest run", "timeout 600 npx vitest run", "uv run python -m pytest tests",
                    ".venv/bin/pytest", "node_modules/.bin/vitest run", "uv run --frozen pytest tests/unit -q",
                    "pre-commit run --all-files", "heavy-run --status && uv run pytest tests/",
                    "cd web && npm test", "make -C api test", "docker compose up -d --build",
                    "FOO=1 nice -n 5 npm run build", "echo $(npx tsc --noEmit)", "npm ci",
                    "ls\npytest -x", "./gradlew build"]:
            with self.subTest(cmd=cmd):
                self.assertTrue(guard(cmd))

    def test_allows_wrapped_quoted_and_harmless_commands(self):
        for cmd in ["heavy-run -- npx vitest run", "~/.claude/scripts/heavy-run 'npm test && npm run build'",
                    "cd web && /x/heavy-run -- npm test", "echo 'npx vitest run'", "rg pytest src",
                    "cat > f.sh <<'EOF'\npytest tests\nnpm run build\nEOF", "npx vitest --version",
                    "HEAVY_BYPASS=1 npx vitest run", "pytest --co -q", "npm run dev", "git status",
                    "docker compose up -d"]:
            with self.subTest(cmd=cmd):
                self.assertFalse(guard(cmd))

    def test_commit_and_push_are_heavy_only_when_a_hook_runs(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            self.assertFalse(guard("git commit -m x", d))
            self.assertFalse(guard("git push", d))
            for name in ("pre-commit", "pre-push"):
                p = os.path.join(d, ".git", "hooks", name)
                open(p, "w").write("#!/bin/sh\n")
                os.chmod(p, 0o755)
            self.assertTrue(guard("git commit -m x", d))
            self.assertTrue(guard(f"git -C {d} push origin HEAD", "/tmp"))
            self.assertFalse(guard("git commit --no-verify -m x", d))
            self.assertFalse(guard("git commit -nm x", d))
            self.assertFalse(guard("git push --no-verify", d))


def size(label, **env):
    return subprocess.run([RUN, "--size", label], capture_output=True, text=True,
                          env=dict(os.environ, **env)).stdout.strip()


class SizeTest(unittest.TestCase):
    def test_narrow_runs_are_small_whole_runs_are_big(self):
        small = ["npx vitest run src/a.test.ts", "uv run pytest tests/test_x.py -q", "pytest tests -k login",
                 "npx vitest run -t 'saves draft'", "pytest tests/test_x.py::test_y", "npx tsc --noEmit",
                 "npx vitest run src/a.test.tsx > /tmp/out 2>&1; tail -5 /tmp/out"]
        big = ["npx vitest run", "uv run pytest tests/", "npx vitest run src/pages src/components",
               "npm run build", "npm run typecheck", "git commit -m x", "npx playwright test",
               "npx tsc --noEmit && npx vitest run"]
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
        self.env = dict(os.environ, HEAVY_DIR=self.dir, HEAVY_TOKENS="3", HEAVY_BIG="2", HEAVY_WAIT_MAX="30")

    def go(self, label, out, **env):
        t0 = time.time()
        p = subprocess.run([RUN, label], capture_output=True, text=True, env=dict(self.env, **env))
        out.append((time.time() - t0, p.stdout.strip(), p.returncode))

    def parallel(self, labels, **env):
        out = []
        ts = [threading.Thread(target=self.go, args=(l, out), kwargs=env) for l in labels]
        t0 = time.time()
        for t in ts:
            t.start()
            time.sleep(0.2)
        for t in ts:
            t.join()
        return time.time() - t0, out

    def test_small_runs_share_the_pool(self):
        took, out = self.parallel(["sleep 1.5 # pytest a.py"] * 3, HEAVY_SIZE="small")
        self.assertLess(took, 2.9)

    def test_two_big_runs_do_not_fit_together(self):
        took, out = self.parallel(["sleep 1.5; echo $HEAVY_WORKERS"] * 2, HEAVY_SIZE="big")
        self.assertGreater(took, 3.0)
        self.assertEqual([o[1] for o in out], ["2", "2"])

    def test_low_memory_waits_only_when_others_hold_tokens(self):
        self.go("true", [], HEAVY_MEM_MIN="101")  # alone: admitted at once
        took, out = self.parallel(["sleep 1.5", "true"], HEAVY_SIZE="small", HEAVY_MEM_MIN="101")
        self.assertGreater(took, 1.5)

    def test_gives_up_after_wait_limit(self):
        out = []
        t = threading.Thread(target=self.go, args=("sleep 4", out), kwargs={"HEAVY_SIZE": "big", "HEAVY_BIG": "3"})
        t.start()
        time.sleep(0.5)
        r = subprocess.run([RUN, "true"], env=dict(self.env, HEAVY_WAIT_MAX="1"), capture_output=True)
        t.join()
        self.assertEqual(r.returncode, 75)


if __name__ == "__main__":
    unittest.main()
