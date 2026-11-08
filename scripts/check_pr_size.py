"""Enforce the complete PR's added + deleted line budget using Git only."""
import argparse
import subprocess
import sys


LIMIT = 500


def changed_lines(base, head):
    # Three-dot matches the PR merge-base diff; no path or file-type exclusions.
    result = subprocess.run(
        ["git", "diff", "--numstat", "-z", "--no-renames", "--no-ext-diff",
         "--no-textconv", "--ignore-submodules=none", f"{base}...{head}", "--"],
        check=True, capture_output=True,
    )
    total = 0
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        added, deleted, _path = record.split(b"\t", 2)
        if not added.isdigit() or not deleted.isdigit():
            raise ValueError("Binary/unmeasurable changes require a separate review policy.")
        total += int(added) + int(deleted)
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="PR target commit or ref")
    parser.add_argument("--head", default="HEAD", help="PR head commit or ref")
    args = parser.parse_args()
    # Reject option/revision-expression injection; resolve each input as a commit.
    try:
        commits = [subprocess.run(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip() for ref in (args.base, args.head)]
        total = changed_lines(*commits)
    except (OSError, subprocess.CalledProcessError, ValueError):
        print("PR size: ERROR; cannot measure the complete diff (check refs/history/binary files).",
              file=sys.stderr)
        return 2
    print(f"PR size: {total} added + deleted lines; limit {LIMIT}.")
    if total > LIMIT:
        print("Split this PR into independently reviewable changes.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
