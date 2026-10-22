# Compatibility

The menu and counter have been reported working on **3.27.3.0** and
**3.28.0.172**. Other hardware and firmware combinations have not been verified.
The package contains no native binary; device support still depends on XOVI and
the firmware's QML interface.

The package requires `3.27 <= remarkable-os < 3.29`. Each QMD adapter also has an
exact version guard: `3.27.3.0` / `3.27.30`, or `3.28.0.172`. A version inside the
package range can install without displaying the counter if its patch is not
supported. Remove this package before moving outside the supported range.

## Known limitations

- The counter reads saved `.rm` files. It cannot see unsaved keystrokes; the
  two-second polling interval is additional to native autosave time.
- An early alpha received one report of a count decreasing after words were
  added to a long page. That case has not been reproduced or specifically
  confirmed resolved. Synthetic long-page append/undo tests pass. Reports with
  a small, non-private example are welcome.
- Continuous CJK/Thai text is counted as a run. The counter uses Unicode
  character categories, not dictionary segmentation or full UAX #29 rules.
- Only typed root text is counted. PDF/EPUB body text and unconverted handwriting
  are excluded.
- Unreadable, incomplete or unsupported files show `Words —` and are retried.
  Limits are 32 MiB per page and 250,000 text positions.
- Other devices, orientation changes and every combination of UI mods have not
  been tested exhaustively.

## How the integration works

[XOVI's qt-resource-rebuilder](https://github.com/asivery/rm-xovi-extensions/tree/master/qt-resource-rebuilder)
applies the QMLDiff adapters at startup. They add the menu toggle and overlay.
The QML/JavaScript reader reconstructs saved text using the v6 root-text format
and sequence ordering documented by rmscene. It never writes notebook files.
The toggle is stored in `/home/root/.config/rm-wordcount.conf`.

The hashed UI selectors come from these public extensions:

| Hook | Source |
| --- | --- |
| Toolbar, settings menu, More Tools menu, close action | [touchLock.qmd](https://github.com/rmitchellscott/xovi-qmd-extensions/blob/67d39e943d8fda30936ad7f51a30f59f0292a9f8/3.28/touchLock.qmd) |
| Notebook host, document ID and page-ID bindings | [navHistory.qmd](https://github.com/alefaraci/xovi-qmd-extensions/blob/0817207c6345f198d5cafeca5cd278deba2cae0b/3.28/navHistory.qmd) |

The corresponding 3.27 selectors match. Each adapter carries its own version
guard. No extracted firmware QML, device hashtable, device identifier or private
notebook is distributed. Test fixtures are public rmscene data or synthetic
examples; provenance is recorded in [THIRD_PARTY.md](../THIRD_PARTY.md).

Local checks cover text parsing, word boundaries, long-page edits, refresh,
stale results, menu toggles, preference persistence and package contents.
The patch tests use a synthetic UI; they cannot establish compatibility with
an untested firmware. See [development checks](development.md).

For a new firmware, check the actual menu and page bindings before adding a
separate adapter and widening the package dependency. Then test typing, deleting,
undo, paste, page switching, both menus, orientation and toggle persistence.
