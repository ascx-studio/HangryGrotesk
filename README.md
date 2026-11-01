<div align="center">

# HANGRY GROTESK

*A geometric stencil display font with a little bite.*

![Python](https://img.shields.io/badge/Python-1E202B?style=for-the-badge&logo=python&logoColor=3776AB)

</div>

## Overview

Hangry Grotesk is a custom display typeface for bold headlines, identities, and
short expressive text. It is built from the glyph outlines in the project SVG
and ships as a UFO source, a regular desktop TTF font, and WOFF/WOFF2 web fonts
conforming to the [Google Fonts Onboarding Guide](https://googlefonts.github.io/gf-guide/onboarding.html).

## Features

- **Distinctive stencil lettering** — Draw attention with geometric, cut-through forms.
- **Google Fonts Latin Core coverage** — Includes all 319 codepoints in `GF_Latin_Core` (A–Z, a–z, 0–9, extended Latin diacritics, punctuation, currency, and math symbols).
- **Desktop, web, and UFO formats** — Outputs `sources/HangryGrotesk.ufo`, `fonts/ttf/HangryGrotesk-Regular.ttf`, `fonts/webfonts/HangryGrotesk-Regular.woff2`, and `dist/` bundles.
- **Interactive specimen** — Preview the typeface, inspect individual glyphs, and adjust a sample.
- **OFL 1.1 licensed** — Use and distribute the font under the terms in [OFL.txt](OFL.txt).

## Preview

Build the project, then open [dist/preview.html](dist/preview.html). Click a glyph
to add it to the editable sample, adjust size and spacing, or copy the CSS declaration.

## Tech stack

- **Build runtime:** Python 3
- **Font compilation:** `fontTools`, `ufoLib2`, `ufo2ft`, `fontmake`
- **Quality assurance:** `fontbakery` (`check-googlefonts` profile)
- **Web delivery:** CSS `@font-face`, WOFF2 and WOFF

## Getting started

### Prerequisites

- Python 3.10 or newer

### Build the font files

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 src/build_font.py
```

The build writes:
- `sources/HangryGrotesk.ufo` (UFO3 source)
- `fonts/ttf/HangryGrotesk-Regular.ttf` (Google Fonts binary)
- `fonts/webfonts/HangryGrotesk-Regular.woff2` (Webfont binary)
- `dist/` (TTF, WOFF, WOFF2, CSS, HTML specimen, and `dist/HangryGrotesk-0.1.0.zip`)

## Use on the web

Copy `dist/hangrygrotesk.css` and the adjacent `dist/fonts/` directory into
your site, then include the stylesheet:

```html
<link rel="stylesheet" href="/fonts/hangrygrotesk.css">
```

```css
body {
  font-family: "Hangry Grotesk", sans-serif;
}
```

## License

Copyright 2026 The Hangry Grotesk Project Authors (https://github.com/ascx-studio/HangryGrotesk).
Licensed under the [SIL Open Font License 1.1](OFL.txt).
