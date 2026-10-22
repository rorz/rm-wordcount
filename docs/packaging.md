# Releasing and publishing to Vellum

The source lives at [rorz/rm-wordcount](https://github.com/rorz/rm-wordcount).
`package.json` supplies the release version, description and maintainer.

## GitHub release

1. Run the [development checks](development.md), including QMLDiff and Qt.
2. Commit the reviewed source, tag it `v0.1.0`, and push the commit and tag.
3. Run `npm run test:package` from that clean checkout. Create a GitHub release
   for the tag and attach these files from `dist/`:

   - `rm-wordcount-0.1.0-r0.apk`
   - `rm-wordcount-0.1.0.tar.gz`
   - `SHA256SUMS`

Use [CHANGELOG.md](../CHANGELOG.md) for the release notes. The custom `.tar.gz`
contains the full source, build scripts, tests and licences. Upload that exact
file: the Vellum recipe pins its SHA-512 checksum. Do not substitute GitHub's
automatically generated source download or replace a published release asset.

The APK is unsigned for installation with `--allow-untrusted`. It installs only
extension files and licence notices. It contains no install hooks and does not
restart the UI or change notebooks.

Builds are deterministic. The timestamp is fixed in `scripts/build.py` and can
be overridden with `SOURCE_DATE_EPOCH`; use the same value for all artifacts of
a release. `dist/` and `test-results/` are ignored by Git and excluded from the
source archive. Only source, documentation, licences and public/synthetic test
fixtures are included; device dumps, logs and private notes must stay outside
the repository.

## Vellum catalogue

reManager uses [Vellum's package repository](https://github.com/vellum-dev/vellum).
Uploading an APK to GitHub does not add it to that catalogue.

After the GitHub release is public:

1. Fork `vellum-dev/vellum` and create `packages/rm-wordcount/`.
2. Copy `dist/vbuild/rm-wordcount/VELBUILD` into that directory. It already has
   the upstream URL, maintainer, firmware bounds, versioned documentation URLs
   and source checksum. Commit only the recipe to Vellum, not the tarball.
3. On a host with [VBuild](https://github.com/Eeems/vbuild) and a running Docker
   or Podman engine, run this from the Vellum checkout:

   ```sh
   vbuild -C packages/rm-wordcount
   ```

   The default command runs the complete build. It downloads the release
   source and signs the APK with the local VBuild key. Test that package on a
   supported firmware. The repository's build process handles catalogue signing.
4. Open a pull request to Vellum with the new recipe and your test results.

Vellum's [contribution rules](https://github.com/vellum-dev/vellum#contributing)
require a person to open the PR, write its description and follow-up comments,
and author the commits. Write the submission yourself; an LLM-written PR
description is grounds for closure under their current policy.

The generated recipe's remote URLs become usable when the tag and release
assets are published. A full VBuild fetch/build against those URLs is a separate
check from this project's local package tests.

## Later versions

Update `package.json`, `CHANGELOG.md` and the versioned examples in this document
and the README, then rebuild. Vellum uses semantic versions; firmware support
changes warrant a patch release. Packaging-only changes in Vellum can increment
`pkgrel`. Keep the exact QMD guards and OS dependencies in agreement.
