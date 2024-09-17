import os
import sys

import git


def get_latest_commit_hash(directory):
    repo = git.Repo(os.getcwd())
    repo.remotes.origin.fetch()
    repo.git.checkout("origin/main")
    commits = repo.git.log("-1", "--", directory).splitlines()

    if not commits:
        return None

    latest_commit_hash = commits[0].split()[1]
    latest_commit = repo.commit(latest_commit_hash)

    added_files = latest_commit.stats.files.keys()

    files_in_directory = [file for file in added_files if file.startswith(directory)]
    latest_file = max(files_in_directory, key=lambda x: latest_commit.committed_date)
    commit_hash = os.path.basename(latest_file).split("_", 1)[0]

    return commit_hash


if __name__ == "__main__":
    # If the script is executed directly, print the latest commit hash
    latest_commit_hash = get_latest_commit_hash(
        "thirdai_platform/database/alembic/versions"
    )
    print(latest_commit_hash)
    sys.stdout.flush()  # Ensure the output is flushed to the standard output
