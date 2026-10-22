# rm-wordcount

A small word count for your notes. Show or hide it from the notebook menu.

Counts typed text on the current page, including handwriting converted to text.
The count appears in the bottom-right corner and updates after the tablet saves.
Everything runs on the tablet. Notebook files are only ever read.

## Use

Open a notebook's settings menu or **More Tools**, then tap **Show word count**.
Tap **Hide word count** to turn it off. The choice is remembered across notebooks
and restarts.

- Counts the whole page, including text below the screen.
- Checks for saved changes every two seconds. Native autosave can add a delay.
- Contractions and hyphenated words count as one. Punctuation and emoji do not.
- Unconverted handwriting and PDF/EPUB body text are not counted. Continuous
  CJK/Thai text is counted as a run, without dictionary-based word segmentation.

`Words …` means loading. `Words —` means the saved page could not be read; it will
try again. See [compatibility and known limitations](docs/compatibility.md).

## Install with reManager

Supports **3.27.3.0** and **3.28.0.172**, using XOVI and qt-resource-rebuilder.
It is not yet in Vellum's public catalogue.

1. Install **XOVI** and **qt-resource-rebuilder** through reManager.
2. Download `rm-wordcount-0.1.0-r0.apk` from the
   [release page](https://github.com/rorz/rm-wordcount/releases/tag/v0.1.0).
3. Upload it to `/home/root/` using reManager's file browser. In its terminal, run:

   ```sh
   /home/root/.vellum/bin/vellum add --allow-untrusted /home/root/rm-wordcount-0.1.0-r0.apk
   ```

4. Close your notebook, then run `/home/root/xovi/start` to load the extension.
   Follow reManager's hashtable rebuild prompt after firmware or XOVI updates.
5. Reopen a notebook and choose **Show word count**.

The download is an unsigned APK; `--allow-untrusted` applies only to that install.
The same command upgrades an earlier version and keeps the on/off preference.

To uninstall, close your notebook and run:

```sh
/home/root/.vellum/bin/vellum del rm-wordcount
/home/root/xovi/start
```

Uninstalling leaves notebooks and the preference alone. Before upgrading to an
unsupported firmware, remove the package: its OS dependency can otherwise block
Vellum's package upgrade. If that has already happened, uninstall it, retry the
upgrade in reManager, then install a compatible release.

## Build

Requires Node 20+ and Python 3.12+. The tablet needs neither.

```sh
npm test
npm run test:package
```

This checks the code and builds the APK, full source archive, checksums and
Vellum recipe in `dist/`. No npm dependencies are needed. `npm run build` builds
without running tests.

See [development checks](docs/development.md) and
[publishing to Vellum](docs/packaging.md). Licensed under GPL-3.0-only;
[third-party sources and licences](THIRD_PARTY.md).
