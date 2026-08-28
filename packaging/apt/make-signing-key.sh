#!/bin/bash
# Create the GPG key that signs the apt repository and store it as GitHub
# Actions secrets. Run this yourself: the private key is a credential and should
# not pass through anyone else's hands.
#
# The key is protected by a random passphrase this script generates, stores as a
# second secret, and never prints. That is not optional politeness -- gpg 2.4,
# which GitHub's ubuntu-24.04 runners carry, re-protects an unprotected secret
# key as it imports it, after which the agent cannot unlock it without a
# terminal and every signing attempt fails. A key that already carries a
# passphrase imports and signs cleanly on every version.
#
# Neither the private key nor the passphrase is ever written to disk: both go
# from the temporary keyring straight into `gh secret set` over a pipe.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${APT_KEY_REPO:-minhngoc2512/status-bar}"

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
echo allow-loopback-pinentry >"$WORK/gpg-agent.conf"

PASSPHRASE="$(head -c 32 /dev/urandom | base64 | tr -d '\n=')"

echo "==> generating a sign-only RSA-4096 key (this can take a moment)"
gpg --batch --quiet --pinentry-mode loopback --passphrase "$PASSPHRASE" \
	--quick-generate-key "$NAME <$EMAIL>" rsa4096 sign never
FPR="$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr:/{print $10; exit}')"
echo "    fingerprint $FPR"

gpg --export --armor "$FPR" >"$HERE/status-bar-archive-keyring.asc"
echo "==> public key written to packaging/apt/status-bar-archive-keyring.asc"

echo "==> storing secrets on $REPO"
gpg --batch --quiet --pinentry-mode loopback --passphrase "$PASSPHRASE" \
	--export-secret-keys --armor "$FPR" \
	| gh secret set APT_GPG_PRIVATE_KEY --repo "$REPO"
printf '%s' "$PASSPHRASE" | gh secret set APT_GPG_PASSPHRASE --repo "$REPO"
echo "    APT_GPG_PRIVATE_KEY, APT_GPG_PASSPHRASE"

gpgconf --kill gpg-agent >/dev/null 2>&1 || true

cat <<MSG

==> done. The temporary keyring is being deleted; nothing is left on disk, and
    the passphrase was never printed.

    Next:
      git add packaging/apt/status-bar-archive-keyring.asc
      git commit -m "Rotate the apt repository signing key"
      git push
      gh workflow run apt.yml

MSG
