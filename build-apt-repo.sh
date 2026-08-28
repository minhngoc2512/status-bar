#!/bin/bash
# Build a flat apt repository into ./public, ready to be served by GitHub Pages.
#
# Flat rather than the usual dists/<suite>/<component>/binary-<arch> tree: this
# project ships one architecture-independent package, so the tree would be all
# ceremony and no benefit. Clients point at the directory itself:
#
#   deb [signed-by=...] https://<user>.github.io/status-bar/ ./
#
# Signing is optional here so the layout can be checked without a key, but a
# repository published unsigned forces every user to add [trusted=yes], which
# turns off exactly the check that matters. CI always signs.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${APT_REPO_DIR:-$HERE/public}"
SOURCE="${APT_REPO_SOURCE:-$HERE/dist}"
SIGN_KEY="${APT_SIGN_KEY:-}"

ORIGIN="status-bar"
LABEL="status-bar"
SUITE="stable"
BASE_URL="${APT_REPO_URL:-https://minhngoc2512.github.io/status-bar}"

for tool in dpkg-scanpackages apt-ftparchive; do
	command -v "$tool" >/dev/null || {
		echo "$tool missing: sudo apt install dpkg-dev apt-utils" >&2
		exit 1
	}
done

shopt -s nullglob
debs=("$SOURCE"/*.deb)
[[ ${#debs[@]} -gt 0 ]] || {
	echo "no .deb found in $SOURCE -- run ./build-deb.sh first" >&2
	exit 1
}

rm -rf "$OUT"
mkdir -p "$OUT/pool"
cp "${debs[@]}" "$OUT/pool/"

cd "$OUT"

# --multiversion keeps every version in the index, so an older release stays
# installable with `apt install status-bar=2.1.0`.
dpkg-scanpackages --multiversion pool /dev/null >Packages 2>/dev/null
gzip -9kf Packages

apt-ftparchive \
	-o "APT::FTPArchive::Release::Origin=$ORIGIN" \
	-o "APT::FTPArchive::Release::Label=$LABEL" \
	-o "APT::FTPArchive::Release::Suite=$SUITE" \
	-o "APT::FTPArchive::Release::Architectures=all amd64 arm64 armhf i386" \
	-o "APT::FTPArchive::Release::Components=main" \
	-o "APT::FTPArchive::Release::Description=status-bar indicators for Ubuntu/GNOME" \
	release . >Release

# gpg's handling of a passphrase-less key differs across versions: 2.2 signs
# happily with plain --batch, while 2.4 (what GitHub's ubuntu-24.04 runners
# carry) can leave an imported unprotected key in a state where gpg reaches for
# pinentry and dies with "Inappropriate ioctl for device" on a TTY-less runner.
# Rather than guess which one is present, try the plain form and fall back to
# loopback with an empty passphrase.
# Note the fallback passes no --passphrase at all. gpg rejects an empty one --
# `--passphrase ""` and `--passphrase-file /dev/null` both fail with "No
# passphrase given", and `--passphrase-fd` on empty input fails with "Bad
# passphrase". With loopback and no passphrase option, an unprotected key signs.
# stdin is closed so a key that really does want one fails fast instead of
# blocking the job.
sign() {
	local errors
	if errors="$(gpg --batch --yes --default-key "$SIGN_KEY" "$@" 2>&1)"; then
		return 0
	fi
	echo "    plain signing failed, retrying with loopback pinentry:" >&2
	printf '    %s\n' "$errors" >&2
	if gpg --batch --yes --pinentry-mode loopback --default-key "$SIGN_KEY" "$@" </dev/null; then
		return 0
	fi
	echo "    both attempts failed; key state:" >&2
	gpg --list-secret-keys --with-colons | awk -F: '/^sec:/{print "    protection=" $18 " usage=" $12}' >&2
	return 1
}

if [[ -n $SIGN_KEY ]]; then
	sign --clearsign -o InRelease Release
	sign --detach-sign --armor -o Release.gpg Release
	# Binary keyring: what `signed-by=` expects in /usr/share/keyrings.
	gpg --export "$SIGN_KEY" >status-bar-archive-keyring.gpg
	gpg --export --armor "$SIGN_KEY" >status-bar-archive-keyring.asc
	echo "==> signed with $SIGN_KEY"
else
	echo "==> WARNING: unsigned; clients will need [trusted=yes]" >&2
fi

sed -e "s|@BASE_URL@|$BASE_URL|g" "$HERE/packaging/apt/index.html" >index.html
touch .nojekyll # keep Pages from eating files that start with an underscore

echo "==> $OUT"
awk '/^Package:|^Version:|^Filename:|^Size:/' Packages | sed 's/^/    /'
