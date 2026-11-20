# joidy — terminal client

Interactive terminal client and **agent-native interface** for the Joidy API
(Python + Typer). One binary, two operating modes:

- **Interactive** — bare `joidy` on a TTY opens a guided picker for notes,
  goals, streaks, auth and stack status.
- **Script/agent** — every command accepts flags for all inputs, emits JSON
  on stdout, writes errors to stderr, and never prompts when stdin/stdout is
  not a TTY. `joidy commands --json` returns the machine-readable command
  tree — the CLI equivalent of MCP tool discovery.

## Install

```bash
# from the repo (editable)
pipx install ./cli

# from GitHub once merged
pipx install 'git+https://github.com/Axel-DaMage/joidy#subdirectory=cli'

joidy --version
joidy --help
```

> The Python `joidy` entry point coexists with the bash stack CLI
> (`scripts/joidy.sh`): whichever comes first on `PATH` wins for `joidy`,
> and the data-plane commands `up/down/status/logs` forward to the bash
> script, so no functionality is lost either way.

## Auth

```bash
joidy auth login                  # prompts for the API password
printf 'pw' | joidy auth login --password -   # non-interactive
joidy auth status                 # API URL, token source, reachability
joidy auth logout
```

The JWT is stored in `~/.config/joidy/config.toml` (mode 0600). Environment
variables override the file — this is how agents target any instance:

```bash
export JOIDY_API_URL=http://localhost:8000   # or a remote instance
export JOIDY_TOKEN=<jwt>
```

## Examples

### Humans

```bash
joidy                              # interactive picker
joidy notes ls
joidy notes new --title "Idea" --content "try X" --tag ideas
joidy goals new --title "Read 30m" --temporality DAILY --target 30
joidy goals ls --state ACTIVE      # ACTIVE = current period instances
joidy goals done 12                # completes the current period instance
joidy streaks checkin 3 --mood 4
joidy streaks history 3 --days 30
```

### Agents / scripts

```bash
# discovery — stable JSON schema, no scraping needed
joidy commands --json | jq '.commands[].path'

# capture a note from a file (content "-" = stdin)
cat daily.md | joidy notes new --title "Daily" --content - --json

# client-side field selection (JMESPath, like `gh --jq`/`aws --query`)
joidy goals ls --json --jq '[?state==`ACTIVE`].id'
joidy streaks ls --jq '[].{id: id, name: name, streak: current_streak}'

# fully non-interactive mutation
joidy notes rm 7 --yes

# completion
joidy completion bash > ~/.local/share/bash-completion/completions/joidy
```

## Conventions (stable contract)

- **Output**: `--json` on every command; JSON is also the default whenever
  stdout is not a TTY. `--jq <expr>` applies a JMESPath filter.
- **Prompts**: skipped when non-interactive; required values error out with
  exit 2 instead of blocking. Destructive ops (`rm`) require `--yes` when
  stdin is not a TTY.
- **Errors**: human-readable text on stderr only; stdout stays parseable.
- **Exit codes**:

  | code | meaning |
  |------|---------|
  | 0 | success |
  | 1 | generic error |
  | 2 | usage error (bad args, API 400/422) |
  | 3 | authentication required or rejected (401/403) |
  | 4 | resource not found (404) |
  | 5 | server error or API unreachable |

- **Temporality goals**: each DAILY/WEEKLY/MONTHLY/ANNUAL goal row *is* a
  period instance — `goals done <id>` completes the current one; the API
  spawns the next instance for ROLLOVER/SNOWBALL goals.

## Stack management

`joidy up|down|restart|sleep|wake|status|logs` (also under `joidy system`)
forwards to `scripts/joidy.sh`, resolved via `$JOIDY_STACK_CLI`, `$JOIDY_DIR`,
`~/.config/joidy/path`, `/etc/joidy/path`, `/usr/share/joidy`, or a shell
`joidy` on `PATH`. `joidy status --json` (or piped) emits
`docker compose ps` as a JSON array.

## Development

```bash
pipx install --editable './cli[test]'     # or: pip install -e './cli[test]'
pytest cli/tests -v                       # unit tests (httpx.MockTransport)
JOIDY_SMOKE_API_URL=http://localhost:8000 JOIDY_SMOKE_PASSWORD=<pw> \
    pytest cli/tests/test_smoke.py -v     # live smoke test
```
