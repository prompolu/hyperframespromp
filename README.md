# HyperFrames project skills

All 21 official HyperFrames skills are vendored as real files under `.agents/skills/`, the repository skill discovery directory used by Codex. Each directory contains the complete upstream `SKILL.md`, references, scripts, and assets. Start future motion graphics work by reading `.agents/skills/hyperframes/SKILL.md`. No video or composition has been created.

## Source and installation

- Official instructions: https://github.com/heygen-com/hyperframes#skills
- Source: `heygen-com/hyperframes`
- Pinned revision: `b306438e8b5e2199db1ed07e6eb4332d53131048`
- Upstream license: `HYPERFRAMES-LICENSE`
- Published bundle manifest: `hyperframes-skills-manifest.json`

Read the upstream README before updating. The documented full installer is:

```sh
npx hyperframes skills
```

In this cloud instance that command could not fetch the published manifest, fell back to 10 core skills, then failed to write its global directories under `/home/agent`. It exited zero despite reporting missing skills. A native HTTPS Git clone succeeded, so installation was completed with the official skills installer in project copy mode:

```sh
git clone --depth 1 https://github.com/heygen-com/hyperframes.git /tmp/hyperframes-official
# Run from this repository:
npx --yes skills add /tmp/hyperframes-official --skill '*' --agent codex --copy --yes
```

For updates, use a fresh clone and review the upstream revision. The installer produces a `skills-lock.json` referring to the temporary local source; that nonportable generated lock was omitted in favor of the committed upstream manifest and revision above.

## Validation

Installation reported 21 skills. All 945 installed files were compared byte for byte with the pinned source; all matched, and no symlinks were present. The published 21 skill names each have a nonempty `SKILL.md` with name and description frontmatter.

Codex CLI `skills/list` verification was attempted, but its app server cannot initialize because the cloud-mounted Codex home is read-only (SQLite state and `installation_id` writes fail). Directory-level discovery is verified; runtime discovery has not been confirmed. Open a fresh Codex session in this repository and check its skills list once a writable Codex runtime is available.

These are skill instructions, not an initialized rendering project. Rendering prerequisites, credentials, browser downloads, and video generation remain outside this installation task.
