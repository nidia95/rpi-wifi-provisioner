# Contributing

Contributions are welcome! To get set up:

```bash
cd client
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Before opening a PR:

```bash
ruff check .
black .
pytest -q
```

Shell scripts under `server/` are linted with
[ShellCheck](https://www.shellcheck.net/) in CI — run it locally if you
touch any `.sh` file:

```bash
shellcheck server/install.sh server/uninstall.sh server/src/*.sh
```

## Workflow

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/short-description`.
3. Commit your changes with a clear message.
4. Push and open a Pull Request describing what changed and why.

Please avoid committing real Wi-Fi credentials, tokens, or `.env` files —
see [`SECURITY.md`](SECURITY.md) for the project's security assumptions.
