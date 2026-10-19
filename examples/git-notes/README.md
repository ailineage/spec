# Git notes example (informative)

Manifests for files changed in a commit can travel with the repository as Git notes under `refs/notes/ailineage`, without touching the files themselves (SPEC.md §10).

- The note is attached to the commit.
- The note body is JSON Lines: one manifest per line, one line per changed file that has AI lineage. Blank lines are ignored, so `git notes append` works.
- `artifact.id` is SHA-256 over the file's blob content (the bytes of the file as committed), not Git's object id.

[`note-payload.jsonl`](note-payload.jsonl) holds the three manifests of the `07-chain` fixtures as an example payload.

```sh
# attach manifests to the current commit
git notes --ref=ailineage add -F note-payload.jsonl HEAD

# add one more manifest later
git notes --ref=ailineage append -m "$(cat hello.go.lineage.json | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), separators=(",", ":"), ensure_ascii=False))')" HEAD

# read them back
git notes --ref=ailineage show HEAD

# notes are not pushed or fetched by default
git push origin refs/notes/ailineage
git fetch origin refs/notes/ailineage:refs/notes/ailineage

# compute artifact.id for a file at a commit
git show HEAD:path/to/file | shasum -a 256
```
