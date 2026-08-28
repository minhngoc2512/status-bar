#!/bin/bash
# Create the GPG key that signs the apt repository, then print what to do with
# it. Run this yourself -- the private key is a credential and should not pass
# through anyone else's hands.
#
# The key has NO passphrase, because CI cannot type one. That is the normal
# trade-off for a repository signing key: guard the GitHub secret, and if it
# ever leaks, generate a new key and re-run the apt workflow. Users then need
# to re-import the public key.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="${1:-status-bar apt repository}"
EMAIL="${2:-}"

[[ -n $EMAIL ]] || {
	echo "usage: $0 \"<name>\" <email>" >&2
	exit 1
}

WORK="$(mktemp -d)"
chmod 700 "$WORK"
trap 'rm -rf "$WORK"' EXIT
export GNUPGHOME="$WORK"

echo "==> generating a sign-only key (this can take a moment)"
gpg --batch --quick-generate-key "$NAME <$EMAIL>" rsa4096 sign never
FPR="$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr:/{print $10; exit}')"

gpg --export --armor "$FPR" >"$HERE/status-bar-archive-keyring.asc"
gpg --export-secret-keys --armor "$FPR" >"$WORK/private.asc"

cat <<MSG

==> fingerprint: $FPR

    Public key written to packaging/apt/status-bar-archive-keyring.asc.
    Commit it: users import that file to verify the repository.

    Now store the private key as a GitHub Actions secret. Run this yourself --
    the command below is the only thing that touches the private key:

      gpg --homedir $WORK --export-secret-keys --armor $FPR \\
        | gh secret set APT_GPG_PRIVATE_KEY --repo minhngoc2512/status-bar

    Do it before this script exits, or the temporary keyring is deleted and you
    will have to generate a new key. Press Enter when the secret is set.

MSG
read -r _
echo "==> done; temporary keyring removed"
