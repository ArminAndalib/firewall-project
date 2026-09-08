# Contributing

Thanks for your interest in contributing! Small, focused contributions are welcome.

Getting started

1. Fork the repo and create a branch from `main` (or from `chore/add-infra` while it's being reviewed):

```bash
git checkout -b myfeature/main
```

2. Run the backend locally:

```bash
cd firewall-project/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

3. Run tests:

```bash
cd firewall-project/backend
pytest -q
```

Code style

- Python: use black/isort for formatting. We recommend running pre-commit hooks or `black .` before committing.

Pull requests

- Keep PRs small and focused.
- Include tests for bug fixes and new features where applicable.
- Describe the motivation and the changes in the PR body.

Reporting issues

- Use issue templates to file bugs or feature requests.

Maintainers

- Maintainers will review PRs and aim to respond within a few business days.