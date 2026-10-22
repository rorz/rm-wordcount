#!/usr/bin/env python3
"""Check APK v2 framing, data checksums, files, dependencies and reproducibility."""
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import zlib

from build import build, DEPENDENCIES, DESCRIPTION, MAINTAINER, NAME, PATCHES, PREFIX, ROOT, SOURCE_NAME, URL, VERSION

apk = build()
original = apk.read_bytes()
source = (ROOT / "dist" / SOURCE_NAME).read_bytes()
assert build().read_bytes() == original, "build must be reproducible"
assert (ROOT / "dist" / SOURCE_NAME).read_bytes() == source, "source archive must be reproducible"

decoder = zlib.decompressobj(31)
control = decoder.decompress(original)
assert decoder.eof and decoder.unused_data, "expected separate control and data gzip streams"
data_stream = decoder.unused_data
decoder = zlib.decompressobj(31)
data = decoder.decompress(data_stream)
assert decoder.eof and not decoder.unused_data, "expected exactly two gzip streams"

with tarfile.open(fileobj=io.BytesIO(control)) as tar:
    assert tar.getnames() == [".PKGINFO"], "no install hooks or signatures in the local package"
    info = tar.extractfile(".PKGINFO").read().decode()
assert f"datahash = {hashlib.sha256(data_stream).hexdigest()}\n" in info
assert "arch = noarch\n" in info
assert "pkgname = rm-wordcount\n" in info
assert f"pkgver = {VERSION}-r0\n" in info
assert f"pkgdesc = {DESCRIPTION}\n" in info
assert f"maintainer = {MAINTAINER}\n" in info
assert f"url = {URL}\n" in info
assert [line[9:] for line in info.splitlines() if line.startswith("depend = ")] == DEPENDENCIES
assert "remarkable-os<3.28" not in info, "must not block the supported 3.28 upgrade"
assert "depend = remarkable-os<3.29\n" in info

with tarfile.open(fileobj=io.BytesIO(data)) as tar:
    paths = set()
    payload = {}
    for entry in tar:
        path = PurePosixPath(entry.name)
        assert not path.is_absolute() and ".." not in path.parts
        assert entry.isdir() or entry.isfile(), "unexpected link or special file"
        assert entry.uid == entry.gid == 0
        assert entry.mode in (0o644, 0o755)
        if entry.isdir(): continue
        assert str(path).startswith(("home/root/xovi/exthome/qt-resource-rebuilder/", "home/root/.vellum/licenses/rm-wordcount/"))
        assert ".local/share/remarkable" not in str(path) and ".config" not in str(path)
        contents = tar.extractfile(entry).read()
        assert hashlib.sha1(contents).hexdigest() == entry.pax_headers["APK-TOOLS.checksum.SHA1"]
        assert entry.name not in paths
        paths.add(entry.name)
        payload[entry.name] = contents
    expected_code = {"Counter.qml", "scene.mjs", "wordcount.mjs", "worker.mjs", "unicode.mjs", "wordcount.qmd"}
    assert expected_code <= {PurePosixPath(p).name for p in paths}
    for name, patch_source in PATCHES.items():
        assert tar.extractfile(f"{PREFIX}/{name}").read() == (ROOT / patch_source).read_bytes()

recipe = ROOT / "dist/vbuild/rm-wordcount/VELBUILD"
subprocess.run(["sh", "-n", str(recipe)], check=True)
assert f"{hashlib.sha512(source).hexdigest()}  {SOURCE_NAME}" in recipe.read_text()
for line in (ROOT / "dist/SHA256SUMS").read_text().splitlines():
    digest, name = line.split("  ")
    assert hashlib.sha256((ROOT / "dist" / name).read_bytes()).hexdigest() == digest

with tempfile.TemporaryDirectory(prefix="rm-wordcount-package-") as temp:
    temp = Path(temp)
    with tarfile.open(fileobj=io.BytesIO(source)) as tar:
        source_paths = set(tar.getnames())
        prefix = f"{NAME}-{VERSION}"
        for required in ("scripts/build.py", "scripts/generate_unicode.py", "README.md", "CHANGELOG.md", "LICENSE", "tests/scene.test.mjs"):
            assert f"{prefix}/{required}" in source_paths, f"missing corresponding source: {required}"
        for name in source_paths:
            path = PurePosixPath(name)
            assert path.parts[0] == prefix and ".." not in path.parts
            assert not {"dist", "test-results", ".git", ".venv", "__pycache__"}.intersection(path.parts)
        tar.extractall(temp / "source", filter="data")

    # Run the real recipe's package function and compare every installed byte.
    subprocess.run(["sh", "-ec", 'srcdir=$1; pkgdir=$2; . "$3"; package', "sh",
                    str(temp / "source"), str(temp / "package"), str(recipe)], check=True)
    installed = {str(p.relative_to(temp / "package")): p.read_bytes()
                 for p in (temp / "package").rglob("*") if p.is_file()}
    assert installed == payload, "Vellum recipe and local APK must install exactly the same files"

    # A recipient can rebuild the APK and source archive without this checkout.
    extracted = temp / "source" / prefix
    subprocess.run([sys.executable, "scripts/build.py"], cwd=extracted, check=True,
                   env=os.environ.copy(), capture_output=True)
    assert (extracted / "dist" / apk.name).read_bytes() == original
    assert (extracted / "dist" / SOURCE_NAME).read_bytes() == source

print("PASS: reproducible APK/source, checksums, safe payload paths, metadata, Vellum recipe and source rebuild")
