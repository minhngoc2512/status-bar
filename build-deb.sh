#!/bin/bash
# Build status-bar_<version>_all.deb into ./dist.
#
# The Debian package is "status-bar", matching the repository, while the
# programs, the systemd unit and ~/.config keep the claude-status name: renaming
# those would orphan every existing user's settings for no benefit.
#
# Plain dpkg-deb, no debhelper: the package is architecture-independent Python
# plus a few data files, so there is nothing to compile and no build-deps to
# install beyond dpkg-dev.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(python3 -c "import re,pathlib; \
print(re.search(r'__version__ = \"([^\"]+)\"', \
pathlib.Path('$HERE/claude_status/__init__.py').read_text()).group(1))")"
MAINTAINER="${DEB_MAINTAINER:-$(git -C "$HERE" config user.name 2>/dev/null || echo "$USER") <${DEBEMAIL:-$(git -C "$HERE" config user.email 2>/dev/null || echo "$USER@localhost")}>}"

command -v dpkg-deb >/dev/null || {
	echo "dpkg-deb missing: sudo apt install dpkg-dev" >&2
	exit 1
}

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

LIB="$STAGE/usr/lib/claude-status"
install -d "$STAGE/DEBIAN" "$LIB" "$STAGE/usr/bin" \
	"$STAGE/usr/lib/systemd/user" \
	"$STAGE/usr/share/applications" \
	"$STAGE/usr/share/icons/hicolor/scalable/apps" \
	"$STAGE/usr/share/doc/status-bar"

# --- payload ---------------------------------------------------------------
cp -r "$HERE/claude_status" "$LIB/"
cp -r "$HERE/icons" "$LIB/"
cp -r "$HERE/hooks" "$LIB/"
install -m 644 "$HERE/indicator.py" "$HERE/merge_settings.py" "$HERE/gen_icons.py" "$LIB/"
find "$LIB" -name '__pycache__' -type d -prune -exec rm -rf {} +
chmod 755 "$LIB/hooks/emit.sh"

install -m 755 "$HERE/packaging/claude-status" "$STAGE/usr/bin/claude-status"
# Second name so `status-bar` works too, now that the package is called that.
ln -sf claude-status "$STAGE/usr/bin/status-bar"
install -m 755 "$HERE/packaging/claude-status-hooks" "$STAGE/usr/bin/claude-status-hooks"
install -m 644 "$HERE/packaging/claude-status.service" "$STAGE/usr/lib/systemd/user/"
install -m 644 "$HERE/packaging/claude-status.desktop" "$STAGE/usr/share/applications/"
install -m 644 "$HERE/icons/claude-working.svg" \
	"$STAGE/usr/share/icons/hicolor/scalable/apps/claude-status.svg"
install -m 644 "$HERE/README.md" "$STAGE/usr/share/doc/status-bar/"
install -m 644 "$HERE/packaging/copyright" "$STAGE/usr/share/doc/status-bar/copyright"

# mktemp gives 0700 and cp preserves the checkout's group-write bits; both end
# up in the archive verbatim, so normalise every mode before packing.
chmod -R u=rwX,go=rX "$STAGE"
chmod 755 "$STAGE/usr/bin/claude-status" "$STAGE/usr/bin/claude-status-hooks" \
	"$LIB/hooks/emit.sh"

# --- control ---------------------------------------------------------------
sed -e "s|@VERSION@|$VERSION|" -e "s|@MAINTAINER@|$MAINTAINER|" \
	"$HERE/packaging/control" >"$STAGE/DEBIAN/control"
for script in postinst prerm postrm; do
	install -m 755 "$HERE/packaging/$script" "$STAGE/DEBIAN/$script"
done

mkdir -p "$HERE/dist"
OUT="$HERE/dist/status-bar_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT" >/dev/null
echo "==> $OUT"
dpkg-deb --info "$OUT" | sed -n '1,12p'
