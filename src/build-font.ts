import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { deflateSync, inflateSync } from "node:zlib";
import { DOMParser } from "@xmldom/xmldom";
import { createFont, woff2, type TTF } from "fonteditor-core";
import { strToU8, unzipSync, zipSync } from "fflate";

const root = new URL("../", import.meta.url);
const require = createRequire(import.meta.url);
const parsePath = require("fonteditor-core/lib/ttf/svg/path2contours").default as (path: string) => TTF.Contour[];
const read = (path: string) => readFile(new URL(path, root), "utf8");
const pkg = JSON.parse(await read("package.json"));
const license = await read("LICENSE.txt");
const copyright = license.split("\n").find(line => line.startsWith("Copyright"))!;
const family = "Hangry Grotesk";
const stem = "HangryGrotesk-Regular";
const epoch = new Date("2026-10-31T00:00:00Z");
await mkdir(new URL("dist/fonts/", root), { recursive: true });

const digits = "zero one two three four five six seven eight nine".split(" ");
const characters: Record<string, string> = {
  period: ".", hyphen: "-", ...Object.fromEntries(digits.map((name, i) => [name, String(i)])),
};
// Preserve the sheet's row baselines, including descenders and the Q tail.
const rows: [string, number][] = [
  ["abcdefghi", 368], ["jklmnopqr", 516], ["stuvwxyz", 664],
  ["ABCDEFGHI", 894], ["JKLMNOPQR", 1042], ["STUVWXYZ", 1190],
];
const baselines: Record<string, number> = Object.fromEntries(
  rows.flatMap(([names, baseline]) => [...names].map(name => [name, baseline])),
);
Object.assign(baselines, { period: 664, hyphen: 1190 }, Object.fromEntries(digits.map(name => [name, 1412])));

const source = new DOMParser().parseFromString(await read("src/hangrygrotesk.svg"), "image/svg+xml");
const paths = Array.from(source.getElementsByTagName("path"));
const glyphNames = paths.map(path => path.getAttribute("id") || "eight");
assert.equal(new Set(glyphNames).size, 64, "Expected 64 uniquely named glyphs");
const font = createFont();
const data = font.get();
data.glyf.push({ name: "space", unicode: [32, 160], contours: [], advanceWidth: 320,
  leftSideBearing: 0, xMin: 0, xMax: 0, yMin: 0, yMax: 0 });
for (const [index, path] of paths.entries()) {
  const name = glyphNames[index];
  assert.ok(name in baselines, `Unknown glyph: ${name}`);
  const char = characters[name] ?? name;
  assert.equal([...char].length, 1);
  // Parse before rounding to retain the sheet's fractional coordinates.
  const contours = parsePath(path.getAttribute("d")!);
  // Honor counter-winding metadata on SVG glyphs when converting to TrueType.
  if (path.getAttribute("data-reverse-contours") === "1") {
    for (const contour of contours.slice(1)) contour.reverse();
  }
  const points = contours.flat();
  const xMin = Math.min(...points.map(p => p.x));
  // The source eight is explicitly named but drawn at the origin of its own view.
  const baseline = name === "eight" ? Math.max(...points.map(p => p.y)) : baselines[name];
  for (const contour of contours) {
      for (const point of contour) {
        point.x = Math.round((point.x - xMin) * 10 + 60);
        point.y = Math.round((baseline - point.y) * 10);
      }
  }
  const xMax = Math.max(...points.map(p => p.x));
  data.glyf.push({ name, unicode: [char.codePointAt(0)!], contours,
    xMin: 60, xMax, yMin: Math.min(...points.map(p => p.y)), yMax: Math.max(...points.map(p => p.y)),
    leftSideBearing: 60, advanceWidth: xMax + 60 });
}
data.name = {
  fontFamily: family, fontSubFamily: "Regular",
  preferredFamily: family, preferredSubFamily: "Regular",
  uniqueSubFamily: `${stem}-${pkg.version}`,
  fullName: `${family} Regular`, postScriptName: stem,
  version: `Version ${pkg.version}`, copyright,
  manufacturer: pkg.author.name, designer: pkg.author.name,
  description: pkg.description,
  licence: license.trim(), urlOfLicence: "https://opensource.org/license/mit",
  sampleText: "The quick brown fox jumps over the lazy dog. 0123456789",
};
Object.assign(data.head, {
  unitsPerEm: 1000, fontRevision: Number(pkg.version.split(".").slice(0, 2).join(".")),
  created: epoch.getTime(), modified: epoch.getTime(), macStyle: 0,
});
Object.assign(data.hhea, { ascent: 850, descent: -250, lineGap: 0 });
Object.assign(data["OS/2"], {
  version: 4, usWeightClass: 400, usWidthClass: 5, fsType: 0, fsSelection: 0xC0,
  achVendID: "NONE", sTypoAscender: 850, sTypoDescender: -250, sTypoLineGap: 0,
  usWinAscent: 850, usWinDescent: 250, sxHeight: 598, sCapHeight: 762,
});
Object.assign(data.post, { italicAngle: 0, underlinePosition: -100, underlineThickness: 50, isFixedPitch: 0 });
font.sort();

await woff2.init();
const expectedCodes = [32, 45, 46, ...Array.from({ length: 10 }, (_, i) => 48 + i),
  ...Array.from({ length: 26 }, (_, i) => 65 + i), ...Array.from({ length: 26 }, (_, i) => 97 + i), 160];
const files: Record<string, Uint8Array> = {};
for (const type of ["ttf", "woff", "woff2"] as const) {
  const buffer = font.write({ type, toBuffer: true, deflate: input => Array.from(deflateSync(Buffer.from(input))) });
  const reloaded = createFont(buffer, { type, inflate: input => Array.from(inflateSync(Buffer.from(input))) }).get();
  // Every output must retain the complete character set, metadata, and baselines.
  assert.deepEqual(Object.keys(reloaded.cmap).map(Number).sort((a, b) => a - b), expectedCodes);
  assert.equal(reloaded.glyf.length, 66);
  for (const [key, value] of Object.entries(data.name)) assert.equal(reloaded.name[key], value, `${type}: ${key}`);
  assert.equal(reloaded.head.unitsPerEm, 1000);
  assert.equal(reloaded["OS/2"].usWeightClass, 400);
  assert.equal(reloaded["OS/2"].fsType, 0);
  const a = reloaded.glyf[reloaded.cmap[65]];
  assert.equal(a.yMin, 0);
  assert.equal(a.yMax, 762);
  assert.ok(reloaded.glyf[reloaded.cmap[103]].yMin < 0);
  assert.equal(reloaded.glyf[reloaded.cmap[56]].yMin, 0);
  assert.equal(reloaded.glyf[reloaded.cmap[56]].yMax, 762);
  for (const glyph of reloaded.glyf.filter(g => g.name !== ".notdef" && g.contours?.length)) {
    assert.equal(glyph.leftSideBearing, 60);
    assert.equal(glyph.xMin, 60);
  }
  files[`fonts/${stem}.${type}`] = buffer;
}
files["hangrygrotesk.css"] = strToU8(`/* ${family} Regular | ${pkg.author.name} | ${pkg.license} */
@font-face {
  font-family: "${family}";
  src: url("./fonts/${stem}.woff2") format("woff2"),
       url("./fonts/${stem}.woff") format("woff");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
  unicode-range: U+0020, U+002D-002E, U+0030-0039, U+0041-005A, U+0061-007A, U+00A0;
}
`);
files["preview.html"] = strToU8(await read("src/preview.html"));
for (const [path, contents] of Object.entries(files)) await writeFile(new URL(`dist/${path}`, root), contents);
files["README.md"] = strToU8(await read("README.md"));
files["LICENSE.txt"] = strToU8(license);
const zip = zipSync(files, { level: 9, mtime: epoch });
const unpacked = unzipSync(zip);
for (const [path, contents] of Object.entries(files)) assert.deepEqual(unpacked[path], new Uint8Array(contents));
const archive = new URL(`dist/HangryGrotesk-${pkg.version}.zip`, root);
await writeFile(archive, zip);
console.log(`Built and validated TTF, WOFF, WOFF2, metadata, and ZIP: ${fileURLToPath(archive)}`);
