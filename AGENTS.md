# Repository Guidelines

## Project Structure & Module Organization

Hangry Grotesk is a Python-driven font project with a static HTML specimen. Edit glyph outlines in `src/hangrygrotesk*.svg`, font generation in `src/build_font.py`, and the specimen in `src/preview.html`. The build currently produces Regular, Pixel, Dotted, and Diamond families.

Generated UFO sources live in `sources/`; desktop TTFs and webfonts live in `fonts/ttf/` and `fonts/webfonts/`. The ignored `dist/` directory contains distributable fonts, CSS, the specimen, and a versioned ZIP. Release and GitHub Pages automation lives in `.github/workflows/release.yml`.

## Build, Test, and Development Commands

Use Python 3.10 or newer; CI uses Python 3.12.

- `python3 -m venv .venv` creates the local environment.
- `.venv/bin/pip install -r requirements.txt` installs font compilation dependencies.
- `npm run check` checks Python syntax only.
- `npm run build` generates fonts and distribution assets, falling back to the virtual environment when needed.
- `.venv/bin/python3 src/build_font.py` runs the build directly.
- `npm pack --dry-run` runs prepack checks and previews package contents.

Open `dist/preview.html` after building to inspect the specimen. Release scripts bump the package version and push commits and tags; reserve them for intentional releases.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, `snake_case` functions and variables, uppercase constants, and type annotations where useful. Preserve the specimen’s existing HTML, CSS, and JavaScript formatting. No formatter or linter is configured.

Use lowercase SVG filenames such as `hangrygroteskdotted.svg` and family-based output names such as `HangryGroteskDotted-Regular.ttf`. Change source files and regenerate outputs instead of editing generated fonts or UFO files directly.

## Testing Guidelines

There is no automated test suite or coverage threshold. Run the syntax check and full build for generation changes. Inspect every affected variant for glyph outlines, spacing, font loading, and specimen controls. The README mentions FontBakery’s Google Fonts profile, but it is not installed by `requirements.txt` or run in CI.

## Commit & Pull Request Guidelines

History mixes descriptive subjects with prefixes such as `feat:`, `fix:`, and `delete:`. Prefer short, specific subjects describing one change. Pull requests should explain the affected variants, list validation performed, link relevant issues, and include before/after screenshots for visible glyph or specimen changes. Preserve OFL licensing and attribution files.
