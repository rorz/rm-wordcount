# Sources and licences

The v6 text reader and sequence ordering are based on the format research and
algorithms in [ricklupton/rmscene](https://github.com/ricklupton/rmscene), commit
`d7d86ca3a8ca4965d911886a1660bc8acf654c1a`. Its MIT licence is in
`licenses/rmscene-MIT.txt`. The `.rm` fixtures in `tests/fixtures` come from that
repository's `tests/data` directory; they contain upstream test data, not user
notebooks.

The hashed 3.27/3.28 UI selectors and menu insertion approach are adapted from
[rmitchellscott/xovi-qmd-extensions](https://github.com/rmitchellscott/xovi-qmd-extensions),
`3.27/touchLock.qmd` and `3.28/touchLock.qmd`, commit `67d39e943d8fda30936ad7f51a30f59f0292a9f8`,
copyright Mitchell Scott, GPL-3.0-only.
Document/page bindings follow `3.27/navHistory.qmd` and `3.28/navHistory.qmd` in
[alefaraci/xovi-qmd-extensions](https://github.com/alefaraci/xovi-qmd-extensions),
commit `0817207c6345f198d5cafeca5cd278deba2cae0b`, copyright Alessio Faraci,
GPL-3.0-only. No original firmware QML is included.

Unicode character categories in `src/unicode.mjs` are generated from Python's
Unicode 15.0.0 database. The Unicode licence is included in `licenses/unicode.txt`.

The local APK builder follows the APK v2 container format used by
[vellum-dev/vellum-cli](https://github.com/vellum-dev/vellum-cli/blob/main/src/apk/package.rs).
XOVI, QMLDiff, Qt and Vellum are runtime/build tools and are not bundled.
