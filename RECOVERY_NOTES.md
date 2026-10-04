# WORKTREE RECOVERY NOTES (untracked file — do NOT commit)

This worktree was deleted mid-session by the environment. Git metadata was
recreated manually (`gitdir`, `commondir`, `HEAD`, `.git` pointer), so the
worktree is registered again but the tracked file tree is EMPTY except for
the files listed below.

## To fully restore and finish the PR #1025 review fix:

```bash
cd /var/hermes/worktrees/joidy-fix-1025

# 1. Repopulate the whole tree at the branch head (PR head 1ec2c932)
git restore --source=HEAD --worktree --staged :/

#    (equivalent: git checkout HEAD -- . && git reset --mixed HEAD)

# 2. The following files are ALREADY written with the correct
#    merge-base content + only the intended fastapi bump:
#      ai-service/requirements.txt   (fastapi==0.142.2, all other pins at merge-base)
#      api/requirements.txt          (sqlalchemy 2.1.1, alembic 1.20.0, pydantic 2.13.5,
#                                     psycopg2-binary 2.9.13, pyjwt 2.14.0, pywebpush 2.5.0)
#      worker/requirements.txt       (watchfiles 1.3.0, sqlalchemy 2.0.54, psycopg2-binary 2.9.13)
#      frontend/package.json         (check script restored to ... --fail-on-warnings, tiptap ^3.31.3, etc.)
#    `git restore` in step 1 will OVERWRITE them back to the broken PR-head
#    state — so either re-apply them from this worktree's current copies
#    (save them aside before restoring), or checkout the merge-base versions.

# 3. frontend/package-lock.json still needs the merge-base content
#    (downgraded lock entries: tiptap 3.31.3->3.30.5, eslint 10.11.0->10.8.0,
#    globals 17.12.0->17.9.0, svelte 5.57.0->5.56.9, keyv 5.6.0->4.5.4,
#    file-entry-cache 11.1.5->8.0.0, flat-cache 6.1.23->4.0.1, removed
#    cacheable/@cacheable/*/@keyv/*/hashery/hookified/qified entries, etc.)
git fetch origin
MB=$(git merge-base origin/development HEAD)
git checkout "$MB" -- frontend/package-lock.json
#    Optionally also: git checkout "$MB" -- api/requirements.txt \
#      worker/requirements.txt frontend/package.json ai-service/requirements.txt
#    then re-apply ONLY the line: fastapi==0.142.2 in ai-service/requirements.txt

# 4. Verify: git diff origin/development...HEAD --name-only should reduce to
#    ai-service/requirements.txt only (a one-line fastapi 0.141.1 -> 0.142.2 change).
#    Note: remote development ALREADY contains fastapi==0.142.2 in
#    ai-service/requirements.txt, so after rebase-equivalence the PR diff
#    may be empty — that is the expected end state of the reviewer's
#    suggested "rebase on latest development" fix.
```
