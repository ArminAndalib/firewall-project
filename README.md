# Firewall Project

A small full-stack firewall demo: a Flask backend that evaluates rules, a static dashboard (HTML/CSS/JS), and a browser extension. This branch adds repository-level documentation and contribution guidelines to make the project easier to use and contribute to.

See the internal project README at `firewall-project/README.md` for architecture and run instructions for the demo app.

Quick start (development):

```bash
# from the repository root
cd firewall-project/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open the dashboard at http://127.0.0.1:5000 or visit the API at http://127.0.0.1:5000.

Project layout (high level):

- firewall-project/: main project source (backend, dashboard, extension)

Contributing
- See CONTRIBUTING.md for how to run tests, style rules, and how to open a PR.

License
- This repository is licensed under the MIT License. See LICENSE for details.
