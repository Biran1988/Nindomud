# Release privacy

Keep all Easter eggs, secret villages, hidden rewards and discovery instructions
out of the in-game changelog and public release notes. Do not add indirect
announcement entries for those features. Preserve their gameplay implementation.

# In-game changelog is a release requirement

Every publicly visible feature, command fix, gameplay balance change, or user-
visible behavior change must get a short entry in `changelog.py` in the same
source commit as the change (or in the same PR before merge). Increment the
plain-text version suffix from the latest entry; do not edit or renumber
historical entries. Changes must appear in the in-game `changes` command,
not just in commit messages or help files. Preserve the secret-content
exceptions above. Test-only, internal refactoring, and ZIP-refresh commits do
not need player-facing entries.

Before packaging `Nindo_mud.zip`, review all public changes since the
last changelog entry. Verify the release includes matching changelog text.
