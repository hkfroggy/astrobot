# Repository Guidelines

## Project Structure & Module Organization

AstroBot is a Python/pygame dashboard designed for a 1024×600 Raspberry Pi display. `main.py` owns application startup, the event loop, page switching, and widget composition. Shared display dimensions, colors, refresh intervals, location defaults, and panel geometry live in `config.py`. The settings modal and persistence logic are in `settings.py`; runtime overrides are written to the local `settings.json` file.

Dashboard components belong in `widgets/`. Each module defines one panel, such as `widgets/weather.py`, `widgets/moon.py`, or `widgets/satellite.py`, and builds on `widgets/base.py`. Deep-sky images are cached under `assets/dso/`; `download_dso_images.py` populates that directory. Deployment details belong in `INSTALL.md`, while user-facing behavior and data-source documentation belong in `README.md`.

## Build, Test, and Development Commands

Create an isolated environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Run `.venv/bin/python main.py --windowed` for desktop development; omitting `--windowed` starts fullscreen mode. Use `.venv/bin/python download_dso_images.py` to fill the local image cache, or add `--force` to replace cached images. Before submitting, run `.venv/bin/python -m compileall main.py config.py settings.py widgets` to catch syntax and import-time compilation errors.

## Coding Style & Naming Conventions

Follow existing Python conventions: four-space indentation, `snake_case` for functions and variables, `PascalCase` for widget classes, and uppercase names for constants. Keep drawing and data-fetch logic inside the relevant widget rather than expanding `main.py`. Use short docstrings for non-obvious behavior and type hints where they improve interfaces. Preserve the current pygame color tuples and `pygame.Rect`-based layout style. No formatter or linter is configured, so keep changes PEP 8-friendly and focused.

## Testing Guidelines

There is currently no automated test suite or coverage threshold. Perform the compile check above, then smoke-test in windowed mode. Verify both pages (`P`), settings (`S`), fullscreen toggling (`F`), and graceful API failure. For calculation-heavy additions, create a `tests/` directory and use `pytest` with files named `test_<module>.py`.

## Commit & Pull Request Guidelines

Recent commits use concise, imperative summaries such as `Fix satellite widget city labels` and `Reduce CPU usage with dirty-flag widget caching`. Keep each commit scoped to one logical change. Pull requests should explain user-visible behavior, note configuration or data-source changes, list validation performed, and include screenshots for layout or rendering changes. Link relevant issues when available and avoid committing local settings, virtual environments, caches, or generated images.
