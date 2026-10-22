#!/usr/bin/env python3
"""Build an unsigned APK v2, complete source archive and Vellum recipe.

For catalogue releases, run VBuild on the generated VELBUILD to sign the package
with the repository's key. This builder never changes the tablet or host config.
"""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import tarfile

ROOT = Path(__file__).resolve().parents[1]
METADATA = json.loads((ROOT / "package.json").read_text())
NAME = METADATA["name"]
VERSION = METADATA["version"]
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", VERSION):
    raise ValueError("Release builds require a MAJOR.MINOR.PATCH version in package.json")
DESCRIPTION = METADATA["description"]
MAINTAINER = METADATA["author"]
URL = METADATA["homepage"]
SOURCE_NAME = f"{NAME}-{VERSION}.tar.gz"
SOURCE_URL = f"{URL}/releases/download/v{VERSION}/{SOURCE_NAME}"
DEPENDENCIES = ["qt-resource-rebuilder", "remarkable-os>=3.27", "remarkable-os<3.29"]
PATCHES = {
    "wordcount.qmd": "packaging/3.27/wordcount.qmd",
    "wordcount-3.28.qmd": "packaging/3.28/wordcount.qmd",
}
PREFIX = "home/root/xovi/exthome/qt-resource-rebuilder"
EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1792627200"))


def archive(files, control=False, apk_checksums=True):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as tar:
        if not control:
            directories = {str(p) for name in files for p in Path(name).parents if str(p) != "."}
            for directory in sorted(directories):
                info = tarfile.TarInfo(directory)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.mtime = EPOCH
                tar.addfile(info)
        for name, contents in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.mode = 0o644
            info.mtime = EPOCH
            info.size = len(contents)
            if not control and apk_checksums:
                info.pax_headers = {"APK-TOOLS.checksum.SHA1": hashlib.sha1(contents).hexdigest()}
            tar.addfile(info, io.BytesIO(contents))
        # Control tar streams must not contain end-of-archive markers.
        used = tar.offset
    raw = output.getvalue()
    return gzip.compress(raw[:used] if control else raw, mtime=EPOCH)


def payload_sources():
    """Map installed files to their checked-in sources; never include user data."""
    files = {f"{PREFIX}/{name}": path for name, path in PATCHES.items()}
    for path in sorted((ROOT / "src").iterdir()):
        if path.suffix in (".mjs", ".qml"):
            files[f"{PREFIX}/{NAME}/{path.name}"] = str(path.relative_to(ROOT))
    for name in ("LICENSE", "THIRD_PARTY.md", "licenses/rmscene-MIT.txt", "licenses/unicode.txt"):
        files[f"home/root/.vellum/licenses/{NAME}/{name}"] = name
    return files


def source_files():
    """Ship build scripts, tests and licences alongside the runtime sources."""
    paths = [ROOT / name for name in (
        ".gitignore", "LICENSE", "README.md", "CHANGELOG.md", "THIRD_PARTY.md", "package.json",
    )]
    for folder in (".github", "docs", "licenses", "packaging", "scripts", "src", "tests"):
        paths.extend(p for p in (ROOT / folder).rglob("*")
                     if p.is_file() and p.suffix in (".yml", ".md", ".txt", ".qmd", ".py", ".mjs", ".qml", ".rm"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("Source archive must not include symlinks")
    return {f"{NAME}-{VERSION}/{p.relative_to(ROOT)}": p.read_bytes() for p in sorted(paths)}


def build():
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    sources = payload_sources()
    files = {name: (ROOT / path).read_bytes() for name, path in sources.items()}
    source_notice = f"{URL}\n{SOURCE_URL}\nSee THIRD_PARTY.md for upstream sources and licences.\n"
    files[f"home/root/.vellum/licenses/{NAME}/SOURCES"] = source_notice.encode()
    data = archive(files)
    info = [
        f"pkgname = {NAME}", f"pkgver = {VERSION}-r0", "arch = noarch",
        f"pkgdesc = {DESCRIPTION}", f"url = {URL}",
        "license = GPL-3.0-only", "origin = rm-wordcount",
        f"builddate = {EPOCH}", f"size = {sum(len(v) for v in files.values())}",
        f"maintainer = {MAINTAINER}",
        *[f"depend = {dep}" for dep in DEPENDENCIES],
        f"datahash = {hashlib.sha256(data).hexdigest()}",
    ]
    control = archive({".PKGINFO": ("\n".join(info) + "\n").encode()}, control=True)
    apk = dist / f"{NAME}-{VERSION}-r0.apk"
    apk.write_bytes(control + data)
    bundle = archive(source_files(), apk_checksums=False)
    (dist / SOURCE_NAME).write_bytes(bundle)
    (dist / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in (apk, dist / SOURCE_NAME)
    ))

    # The bundled archive is also the GitHub release asset used by Vellum.
    recipe = dist / "vbuild" / NAME
    recipe.mkdir(parents=True, exist_ok=True)
    (recipe / SOURCE_NAME).write_bytes(bundle)
    install_directories = "\n".join(
        f'    mkdir -p "$pkgdir/{directory}"'
        for directory in sorted({str(Path(name).parent) for name in sources})
    )
    install_commands = "\n".join(
        f'    install -m644 "$builddir/{source}" "$pkgdir/{destination}"'
        for destination, source in sorted(sources.items())
    )
    (recipe / "VELBUILD").write_text(f'''# Generated by scripts/build.py; see docs/packaging.md.
maintainer={shlex.quote(MAINTAINER)}
pkgname={NAME}
pkgver={VERSION}
pkgrel=0
upstream_author="rorz"
category="ui"
pkgdesc={shlex.quote(DESCRIPTION)}
url={shlex.quote(URL)}
arch="noarch"
license="GPL-3.0-only"
depends="{' '.join(DEPENDENCIES)}"
readmeurl="https://raw.githubusercontent.com/rorz/rm-wordcount/v$pkgver/README.md"
changelogurl="https://raw.githubusercontent.com/rorz/rm-wordcount/v$pkgver/CHANGELOG.md"
source="$url/releases/download/v$pkgver/{SOURCE_NAME}"
options="!check !fhs"
builddir="$srcdir/$pkgname-$pkgver"

package() {{
{install_directories}
{install_commands}
    printf '%s\\n' "$url" "$source" 'See THIRD_PARTY.md for upstream sources and licences.' > \\
        "$pkgdir/home/root/.vellum/licenses/$pkgname/SOURCES"
}}
sha512sums="{hashlib.sha512(bundle).hexdigest()}  {SOURCE_NAME}"
''')
    print(f"Built {apk.relative_to(ROOT)} ({apk.stat().st_size:,} bytes; unsigned local build)")
    print(f"VBuild input: {recipe.relative_to(ROOT)}")
    return apk


if __name__ == "__main__":
    build()
