# Two targets.
#
#   dev      The development environment, and the default. A full devcontainer base:
#            login shell, git, sudo, common utilities, and automatic UID/GID remapping,
#            so files written into the mounted clone are owned by you rather than root.
#            Used by .devcontainer/. Add tooling through devcontainer features, not
#            through apt here.
#
#   runtime  Minimal: Python and PyYAML, nothing else. For a scripted or automated run
#            where no human is at the keyboard.
#
#              docker build --target runtime -t rfc-subject-tags-runtime .
#              docker run --rm -v "$PWD:/work" rfc-subject-tags-runtime \
#                sh -c 'python3 make_corpus_from_index.py && python3 engine.py && python3 regen.py'
#
# CI uses neither today — the workflow installs Python with actions/setup-python. The
# runtime target is here for scripted runs, and if CI is ever containerised it is the
# stage to point at.
#
# Both targets need network egress to www.rfc-editor.org for the corpus fetch.


# --------------------------------------------------------------------- runtime
# Trixie here, unlike the dev stage below: the official Python image carries no
# third-party apt sources, so its apt works normally.
FROM python:3.14-slim-trixie AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt


# ------------------------------------------------------------------------- dev
# Last stage, so `docker build .` with no --target gives the human environment.
FROM mcr.microsoft.com/devcontainers/python:2-3.14-trixie AS dev

# This image ships an apt source for dl.yarnpkg.com whose signing key is absent.
# Debian 13 verifies signatures with sqv, which refuses an unsigned repository
# outright, so `apt-get update` fails before installing anything — which would break
# any devcontainer feature, since features use apt.
#
# The fix is to drop that source, not to import its key: this is a Python project and
# nothing here installs from yarn, so trusting a third-party signing key to authorise
# a repository we never use would widen the trust surface for no benefit. Removing it
# needs no network and no new trust.
#
# The `apt-get update` below is deliberate: it proves apt works at build time, so this
# fails loudly here rather than later inside someone's container. Drop this whole RUN
# when the upstream image stops shipping the broken source.
RUN grep -rl 'dl\.yarnpkg\.com' /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null \
      | xargs -r rm -f \
 && apt-get update \
 && rm -rf /var/lib/apt/lists/*

# Nothing is installed with apt here: the base already carries git, sudo, a login
# shell and the common utilities. Extra tooling belongs in devcontainer.json as a
# feature rather than a layer here — see .devcontainer/devcontainer.json.

WORKDIR /work
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
