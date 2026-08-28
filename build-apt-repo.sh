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
SIGN_PASSPHRASE="${APT_SIGN_PASSPHRASE:-}"

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

# Signing needs a passphrase-protected key. A key with no passphrase signs fine
# on gpg 2.2 but not on 2.4 (what GitHub's ubuntu-24.04 runners carry): 2.4
# protects an unprotected secret key as it imports it, and the agent then has no
# way to unlock it without a terminal. Measured on the runner, all four
# workarounds fail -- plain signing and --no-tty give "Inappropriate ioctl for
# device", loopback with no passphrase gives "we are in batchmode - can't get
# input", and loopback with an empty one gives "No passphrase given".
#
# APT_SIGN_PASSPHRASE goes in on a file descriptor rather than the command line,
# which would otherwise expose it in the process table.
sign() {
	if [[ -n $SIGN_PASSPHRASE ]]; then
		gpg --batch --yes --pinentry-mode loopback --passphrase-fd 3 \
			--default-key "$SIGN_KEY" "$@" 3<<<"$SIGN_PASSPHRASE"
	else
		gpg --batch --yes --default-key "$SIGN_KEY" "$@" </dev/null
	fi
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
