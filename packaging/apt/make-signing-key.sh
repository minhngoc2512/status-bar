#!/bin/bash
# Create the GPG key that signs the apt repository and store it as a GitHub
# Actions secret. Run this yourself: the private key is a credential and should
# not pass through anyone else's hands.
#
# The key has NO passphrase, because CI cannot type one. That is the normal
# trade-off for a repository signing key: guard the GitHub secret, and if it
# ever leaks, run this again to replace it -- users then re-import the public
# key. The private key is never written to disk; it goes from the temporary
# keyring straight into `gh secret set` over a pipe.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${APT_KEY_REPO:-minhngoc2512/status-bar}"
SECRET="APT_GPG_PRIVATE_KEY"

NAME="${1:-}"
EMAIL="${2:-}"
if [[ -z $NAME || -z $EMAIL ]]; then
	cat >&2 <<USAGE
usage: $0 "<name>" <email>

  e.g. $0 "status-bar apt repository" you@example.com

The address only labels the key; it is never mailed.
USAGE
	exit 1
fi

command -v gpg >/dev/null || { echo "gpg missing: sudo apt install gnupg" >&2; exit 1; }
command -v gh >/dev/null || { echo "gh missing: https://cli.github.com" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "run: gh auth login" >&2; exit 1; }

WORK="$(mktemp -d)"
chmod 700 "$WORK"
trap 'rm -rf "$WORK"' EXIT
export GNUPGHOME="$WORK"

echo "==> generating a sign-only RSA-4096 key (this can take a moment)"
gpg --batch --quiet --quick-generate-key "$NAME <$EMAIL>" rsa4096 sign never
FPR="$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr:/{print $10; exit}')"
echo "    fingerprint $FPR"

gpg --export --armor "$FPR" >"$HERE/status-bar-archive-keyring.asc"
echo "==> public key written to packaging/apt/status-bar-archive-keyring.asc"

echo "==> storing the private key as $SECRET on $REPO"
gpg --export-secret-keys --armor "$FPR" | gh secret set "$SECRET" --repo "$REPO"

cat <<MSG

==> done. The temporary keyring is being deleted; nothing is left on disk.

    Next:
      git add packaging/apt/status-bar-archive-keyring.asc
      git commit -m "Add the apt repository signing key"
      git push

    Then tag a release and CI publishes the repository:
      git tag v2.2.0 && git push --tags

MSG
