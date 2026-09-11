# Contributing

Three documents describe the system itself, and this one describes working on it:

- **[README.md](README.md)** — what the tags are for, the requirements R1–R20, and how search and
  subscription behave. Read this before proposing a vocabulary change.
- **[code.md](code.md)** — the corpus, the `taxonomy.yaml` schema, the assignment algorithm, and
  the discipline for writing match rules.
- **[validation.md](validation.md)** — the checks a rebuild must pass, and the current figures.

## Suggesting a tag without running anything

Open a [new subject tag issue](../../issues/new?template=new-subject-tag.yml). You do not need a
checkout. Say what the tag would cover and which RFCs should carry it; R9–R13 in README.md are the
tests a proposal is judged against.

## Setting up

There are two ways to get a working environment. Pick one — the build commands in the next
section are identical either way.

### With the devcontainer

The repository ships a `.devcontainer/` definition, built from the `dev` target of the
`Dockerfile` at the root. Open your clone in an editor with Dev Containers support — in VS Code,
*Reopen in Container*; or use GitHub Codespaces — and you get a full working environment: Python
and PyYAML installed, git, a login shell, `sudo`, and the clone mounted as the working
directory. Files you create there are owned by you, not root.

The `Dockerfile`'s other target, `runtime`, is a minimal Python-plus-PyYAML image for scripted
runs with no human at the keyboard; the header of the file shows how to use it.

**Nothing else is needed: skip the virtual environment below.** If `requirements.txt` ever
changes, rebuild the container so the new dependency is installed.

### Without the devcontainer

You need Python 3 and the one third-party dependency. A virtual environment keeps it off your
system Python:

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

`.venv/` is gitignored.

## The build

```
python3 make_corpus_from_index.py    # fetches rfc-index.xml, writes rfcs.json
python3 engine.py                    # validates the taxonomy, assigns tags, writes rfc-tags.json
python3 regen.py                     # writes rfc-tags.csv and rfc-tags.html, refreshes figures
```

Every step reads and writes in the working directory. The corpus fetch needs network access to
`www.rfc-editor.org`. Nothing the build produces is committed — `rfc-index.xml`, `rfcs.json`,
`rfc-tags.json`, `rfc-tags.csv` and `rfc-tags.html` are all gitignored. The current build is
published at <https://rfc-editor.github.io/rfc-subject-tags/>.

## Changing the taxonomy

`taxonomy.yaml` is the only file to edit; everything else is derived from it. The table under
*Editing the file* in code.md says what to change for each kind of edit, and the *Rule-writing
discipline* section lists the failure modes each rule convention exists to prevent — read it
before adding a `match` regex.

**`regen.py` rewrites three tracked files in place:** the `stats` blocks in `taxonomy.yaml`, and
the figures in `README.md` and `validation.md`. So:

1. start from a clean working tree;
2. make your change to `taxonomy.yaml`;
3. run the build above;
4. review the *whole* diff, including the three rewritten files, and commit it together.

The figures move whenever the corpus does, so a run against a newer index will show small changes
you did not cause. That is expected. The published page rebuilds daily and therefore runs ahead of
the committed figures; it carries its own build date so the two can be told apart.

## Before you open a pull request

Work through the checks in validation.md. The ones that most often catch a rule change are
**Root leaks**, **Overlap** and **Engine round-trip** — a change to a general rule can move
hundreds of RFCs, and the point is that every difference is explainable.

Mechanical checks, at minimum:

```
python3 engine.py    # must report 0 untagged, 0 unused, 0 zero-topic
```

## Reviewing a pull request

The workflow builds every pull request but does not deploy it: GitHub Pages serves one live site
per repository, so only `main` publishes. Instead the build attaches the staged site to the run.

To look at the page a merge would publish: open the pull request's **Checks** tab, select the
**Build and publish** run, and download the **site-preview** artifact from the Artifacts section
at the bottom of the summary. Unzip it and open `index.html` in a browser — it is self-contained
and needs no server. The artifact is kept for the repository's artifact retention period, so
re-run the workflow if it has expired.

The **Overlap** view is usually the fastest way to see whether a rule change has caused a leak.

## Licensing

Contributions are made under the BSD 3-Clause licence in [LICENSE](LICENSE). Note that
`browser_template.html` embeds three fonts under the SIL Open Font License 1.1; if you touch the
`@font-face` block, the notice above it must stay with the file, because `rfc-tags.html` is
distributed as a single self-contained page and that comment is its only carrier.
