# Contributing to fixmywifi

Thanks for helping make home Wi-Fi less painful. Every kind of contribution is welcome, from a typo fix to a
new platform.

## Set up

```bash
git clone https://github.com/Tolz99/fixmywifi
cd fixmywifi
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
fixmywifi --demo
```

## Add a rule (the easiest way to contribute)

Rules live in `src/fixmywifi/rules/`, grouped by topic:

| File | About |
|---|---|
| `wifi.py` | the radio link: signal, noise, band, channel, width, Wi-Fi generation |
| `internet.py` | delay, packet loss, speed, bufferbloat, DNS |
| `security.py` | how the network is locked |
| `home.py` | things the person told us: size, walls, router spot, setup, habits |

A rule is a function decorated with `@rule`. It gets a `ctx` with `ctx.scan` (measurements) and `ctx.profile`
(answers), and returns a `Finding` or `None`:

```python
@rule
def microwave_hours(ctx: Ctx):
    if ctx.link and ctx.link.band == "2.4" and ctx.profile.problem == "evenings":
        return Finding(
            id="microwave",                 # unique, kebab-case
            severity="tip",                 # critical | warning | tip | good
            title="Microwaves can knock out 2.4 GHz Wi-Fi while they run.",
            why="Microwave ovens leak energy right in the 2.4 GHz band...",
            fix=["Move devices to 5 GHz.", "Keep the router at least 2 m from the kitchen."],
            category="home",                # wifi | internet | security | hardware | home
        )
```

Guidelines:

- **Write for someone who has never opened router settings.** Name things by what they do. Explain jargon by
  what it causes ("devices take turns to talk"), not by definition.
- **Every field in `ctx.scan` can be missing.** Return `None` when you don't have what you need.
- **Free fixes first** in the `fix` list, buying things last.
- **Cite your threshold** in a comment or the PR if it isn't obvious.
- **Add a test** in `tests/test_rules.py` that builds a `Scan`/`Profile` and checks your finding appears.

## Improve a platform scanner

Scanners are in `src/fixmywifi/collectors/`. Each one has pure `parse_*` functions that take command output as
text, so they can be tested on any OS. When fixing a parser, paste the real (anonymised) command output into
`tests/test_parsers.py` as a fixture.

**Please remove your network names and MAC addresses from any output you share.**

## Pull requests

- Keep PRs focused; one rule or fix per PR is perfect.
- Run `pytest` and `ruff check src tests` before pushing.
- Be kind in reviews. See the [Code of Conduct](CODE_OF_CONDUCT.md).
