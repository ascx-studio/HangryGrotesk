<div align="center">

# HANGRY GROTESK

*A geometric stencil display font with a little bite.*

![TypeScript](https://img.shields.io/badge/TypeScript-1E202B?style=for-the-badge&logo=typescript&logoColor=3178C6)
![Node.js](https://img.shields.io/badge/Node.js-1E202B?style=for-the-badge&logo=nodedotjs&logoColor=339933)

</div>

## Overview

Hangry Grotesk is a custom display typeface for bold headlines, identities, and
short expressive text. It is built from the glyph outlines in the project SVG
and ships as a regular desktop font and web fonts.

## Features

- **Distinctive stencil lettering** — Draw attention with geometric, cut-through forms.
- **Desktop and web formats** — Use TTF in desktop apps and WOFF/WOFF2 on the web.
- **Interactive specimen** — Preview the typeface, inspect individual glyphs, and adjust a sample.
- **Lightweight character set** — Includes Latin uppercase and lowercase, digits, period, hyphen, and spaces.
- **MIT licensed** — Use and distribute the font under the terms in [LICENSE.txt](LICENSE.txt).

## Preview

Build the project, then open [dist/preview.html](dist/preview.html). The dark
specimen shows “Hangry Grotesk.” against cap-height, x-height, baseline, and
descender guides. The guides follow the font’s rendered glyph measurements.
Click a glyph to add it to the editable sample, adjust size and spacing, or
copy the CSS declaration.

## Tech stack

- **Build runtime:** Bun and TypeScript
- **Font conversion:** fonteditor-core
- **ZIP packaging:** fflate
- **Web delivery:** CSS `@font-face`, WOFF2 and WOFF

## Getting started

### Prerequisites

- [Bun](https://bun.sh/) 1.2 or newer
- Node.js and npm for creating the optional npm tarball

### Build the font files

```sh
bun install
bun run check
bun run build
```

The build writes TTF, WOFF, WOFF2, CSS, an HTML specimen, and
`dist/HangryGrotesk-0.1.0.zip`.

### Create the npm package

```sh
npm pack --pack-destination dist
```

The package prepack step runs the type check and font build. To install the
result in another project:

```sh
npm install ./dist/hangrygrotesk-0.1.0.tgz
```

Import the CSS in your app:

```js
import "hangrygrotesk";
```

## GitHub Actions release

The `Build and release font` workflow runs for `v*` tags and can also be run
manually from the Actions tab. A tag must match the package version in
`package.json` (for example, `v0.1.0`). Pushing a matching tag builds the font
files and creates a GitHub Release with the ZIP and npm tarball attached. A
manual run builds and uploads the artifacts without creating a release.

```sh
git tag v0.1.0
git push origin v0.1.0
```

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

## Character coverage

The font contains A–Z, a–z, 0–9, period, hyphen, space, and nonbreaking space.
Characters outside this set fall back to another font. Hangry Grotesk has one
regular weight, with no italic, kerning pairs, hinting, or extended language
coverage. The source shapes use proportional advances and uniform sidebearings.

## License

Copyright (c) 2026 Rajeev Puri. Licensed under the [MIT License](LICENSE.txt).
