# Contributing

The first beta targets Ubuntu GNOME on X11 with Python 3.12. Reports from
other environments are welcome, but those environments are unverified until
someone tests them.

Install from a checkout using `./install`, then run:

```sh
.venv/bin/python -m pytest -q
```

The lockfile includes pytest. Lint and package checks use the development tools
listed in `.github/workflows/checks.yml`.

For a bug report, include the project version, distribution, desktop, session
type, Python version, relevant tool call, expected result, and actual result.
Review diagnostics before sharing them. Remove usernames, local paths, window
titles, screenshots, credentials, and other private information.

Live checks take over the pointer and keyboard. Run them only on your own idle
desktop, after stopping any existing controller. The scripts create disposable
GTK windows and separate test state:

```sh
.venv/bin/python tests/live_demo.py
.venv/bin/python tests/safety_demo.py
```

Do not clear the production Stop latch from a script. Do not test against
someone's browser, accounts, or documents. Tests must not submit forms, send
messages, or change system settings. Keep screenshots in ignored `output/`.

Changes to input delivery, cancellation, focus checks, clipboard handling, or
crash recovery need regression coverage. Describe what you verified and what
you could not test. See [SECURITY.md](SECURITY.md) for vulnerability reports.
