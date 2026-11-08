"""Exercise the CLI against disposable Git repositories, without app services."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_pr_size.py"


class PRSizeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="movelle-pr-size-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.env = {key: os.environ[key] for key in
                    ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-q")
        self.git("config", "user.name", "PR size test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                              check=True, capture_output=True, text=True).stdout.strip()

    def write(self, name, count, line="line\n"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(line * count, encoding="utf-8")

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "fixture", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def check(self, expected_status, expected_lines=None, base=None, head="HEAD"):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", base or self.base, "--head", head],
            cwd=self.repo, env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, expected_status, result.stdout + result.stderr)
        if expected_lines is not None:
            self.assertIn(f"{expected_lines} added + deleted lines", result.stdout)
        return result

    def test_empty_diff_passes(self):
        self.check(0, 0)

    def test_exactly_500_includes_additions_and_deletions(self):
        self.write("replace.txt", 250, "old\n")
        self.base = self.commit()
        self.write("replace.txt", 250, "new\n")
        self.commit()
        self.check(0, 500)

    def test_501_fails_across_commits_and_all_file_categories(self):
        for name in ("tests/test_example.py", "docs/contract.md", ".github/config.yml",
                     "migrations/next.sql", "frontend/package-lock.json"):
            self.write(name, 100)
        self.commit()
        self.write("another.txt", 1)
        self.commit()
        self.check(1, 501)

    def test_deleted_files_count(self):
        self.write("removed.txt", 501)
        self.base = self.commit()
        (self.repo / "removed.txt").unlink()
        self.commit()
        self.check(1, 501)

    def test_uses_merge_base_instead_of_base_only_changes(self):
        self.git("checkout", "-qb", "target", self.base)
        self.write("target-only.txt", 700)
        target = self.commit()
        self.git("checkout", "-qb", "feature", self.base)
        self.write("feature-only.txt", 20)
        self.commit()
        self.check(0, 20, base=target)

    def test_reverted_intermediate_changes_do_not_inflate_final_diff(self):
        self.write("temporary.txt", 700)
        self.commit()
        (self.repo / "temporary.txt").unlink()
        self.commit()
        self.check(0, 0)

    def test_rename_counts_both_paths_without_exemptions(self):
        self.write("old name.txt", 251)
        self.base = self.commit()
        (self.repo / "old name.txt").rename(self.repo / "new name.txt")
        self.commit()
        self.check(1, 502)

    def test_binary_diff_fails_closed(self):
        (self.repo / "asset.bin").write_bytes(b"\0binary")
        self.commit()
        self.assertIn("cannot measure", self.check(2).stderr)

    def test_missing_refs_and_history_fail_closed(self):
        self.check(2, base="missing-ref")
        self.check(2, head="missing-ref")
        self.git("checkout", "--orphan", "unrelated")
        self.write("unrelated.txt", 1)
        self.commit()
        self.check(2)

    def test_diff_driver_cannot_hide_text_changes(self):
        self.write(".gitattributes", 1, "*.txt diff=hidden\n")
        self.base = self.commit()
        self.git("config", "diff.hidden.command", "does-not-exist")
        self.write("visible.txt", 501)
        self.commit()
        self.check(1, 501)


if __name__ == "__main__":
    unittest.main()
