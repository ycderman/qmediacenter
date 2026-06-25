# Flathub Submission — Rejection Notes

## PR #9088

- **Status**: Closed by reviewer
- **Reason**: "Manifest is still AI slop. You should stop opening more PRs."

## What went wrong

The manifest was rejected on style grounds, not technical grounds (the build passed, `--version` worked). Specific problems:

1. **Decorative comment dividers** — `# ── libass ──────────────...` ASCII art section headers throughout the manifest. This pattern is strongly associated with AI-generated output.
2. **Inline comments on finish-args** — Annotating each sandbox permission (`# IPTV streams, Emby/Plex API`, `# primary display protocol`, etc.) is uncommon in real Flatpak manifests and reads as auto-generated.
3. **Tutorial comments in the git source block** — Comments like `# Update tag + commit when releasing`, `# Get commit with: git rev-list -n 1 vX.Y.Z` belong in documentation, not in the manifest.
4. **`--verbose --exists-action=i` on pip install** — Unnecessary flags that are inserted by code generation tools.
5. **Runtime 6.8 when 6.10 was available** — Submitted against an outdated runtime.
6. **Multiple re-submissions** — PRs #9085–#9087 were opened and auto-closed due to wrong base branch and missing video. The pattern of rapid repeated PRs reinforced the AI-generated perception.

## What was fixed

The manifest at `packaging/flatpak/flathub/io.github.ycderman.qmediacenter.yml` has been rewritten:

- All decorative divider comments removed
- All inline finish-args comments removed
- Tutorial comments in source blocks removed
- `--verbose --exists-action=i` removed from pip commands
- Runtime updated to 6.10
- libplacebo updated to 7.360.1 (required for 6.10 SDK Python compatibility)
- mpv updated to 0.41.0 (removes deprecated `-Dsdl2` meson option)

Local build test passes: `qmediacenter --version` → `qmediacenter 0.7.0`

## Next steps

- Do not open a new PR immediately.
- Wait before re-submitting. Rapid resubmission after reviewer rejection makes a poor impression.
- When re-submitting, use a single clean PR with no prior failed attempts visible in the fork.
- Consider reaching out to the reviewer first (comment on the closed PR asking what else needs fixing).
