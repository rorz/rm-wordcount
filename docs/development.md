# Development checks

Use Node 20+ and Python 3.12+. There are no npm dependencies.

```sh
npm test
npm run test:package
```

The package check builds twice, verifies reproducibility, inspects the APK's
hashes and file manifest, and checks the Vellum recipe against the same payload.
It also rebuilds from the complete source archive. `npm run build` builds only.

## QML integration

Build [asivery/qmldiff](https://github.com/asivery/qmldiff) at commit
`25681c3cc7addb93fdbb41ceac1f1bdce8b2625d` using `cargo build --release --locked`.
This is the QMLDiff revision from rm-xovi-extensions v19-23052026.

```sh
QMLDIFF=/path/to/qmldiff/target/release/qmldiff npm run test:patch
python3 -m venv .venv
.venv/bin/pip install PySide6-Essentials==6.8.3
.venv/bin/python scripts/test_qt.py
```

Run the patch check before the Qt check. It creates a synthetic patched UI that
Qt then exercises alongside the actual counter and worker. Qt runs offscreen
without a server or tablet connection. On macOS, run outside a restricted shell
sandbox if Qt's CPU-feature probe is blocked.

The tests cover real public rmscene fixtures, insert/delete/undo, Unicode word
boundaries, malformed saves, long pages, page changes during parsing, cached
counts, hidden views, both menu actions and preference persistence. Patch guards
are checked on supported and unsupported firmware versions.

GitHub Actions runs these checks and uploads build artifacts; it does not
publish a release. Output under `test-results/` is local and excluded from the
release. Do not commit device logs, extracted firmware or private notebooks.

`src/unicode.mjs` uses Unicode 15.0.0. Regenerate it with Python 3.12:

```sh
python3 scripts/generate_unicode.py
```
