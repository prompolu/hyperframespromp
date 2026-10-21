# HyperFrames project skills

All 21 official HyperFrames skills are vendored as real files under `.agents/skills/`, the repository skill discovery directory used by Codex. Each directory contains the complete upstream `SKILL.md`, references, scripts, and assets. Start future motion graphics work by reading `.agents/skills/hyperframes/SKILL.md`. The first editable PROMPOLU technical animation is available below.

## Latest video — 60-second photographic version

Rebuilt with real photographic imagery, the website's light ivory/dark ink/bronze identity, French voiceover and original music. 1080 × 1920, 30 FPS, 60 seconds. Photos are credited illustrative stock, not claims of PROMPOLU installations.

- [Full-resolution 60-second MP4](videos/prompolu-thermal-break-60s/renders/PROMPOLU-60s-1080x1920.mp4)
- [Smaller 60-second preview](videos/prompolu-thermal-break-60s/renders/PROMPOLU-60s-preview-540x960.mp4)
- [Editable project ZIP](artifacts/PROMPOLU-60s-editable.zip)
- [Source, credits and rendering instructions](videos/prompolu-thermal-break-60s/README.md)

Open an MP4 on GitHub and select **Download raw file** to play it locally.

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

Codex runtime discovery is verified with the official Codex CLI 0.110.0: its app-server `skills/list` method, called with this repository as `cwd` and `forceReload: true`, returned all 21 repository skills and zero errors. This check required no model invocation or video creation. All 21 bundles also match the published upstream whole-directory hashes, and every installed file is tracked in Git.

The preinstalled Codex CLI 0.163.0 cannot initialize its app server because the cloud-mounted Codex home is read-only (`installation_id` writes fail). Discovery through that specific runtime remains blocked; the compatibility check above used an isolated official 0.110.0 CLI with SQLite state directed to `/tmp`. The installed skill files were unchanged.

The rendering project has its own pinned CLI commands and validation evidence under `videos/prompolu-thermal-break/`.


## PROMPOLU — first motion graphics test

Five-second French technical animation, rendered using HyperFrames at 30 FPS. The schematic is generic and labeled non-contractual.

- [1080 × 1920 MP4](videos/prompolu-thermal-break/renders/prompolu-thermal-break-1080x1920.mp4)
- [540 × 960 preview MP4](videos/prompolu-thermal-break/renders/prompolu-thermal-break-test-540x960.mp4)
- [Download the editable project ZIP](artifacts/prompolu-thermal-break-editable.zip)
- [Editable source and rendering instructions](videos/prompolu-thermal-break/README.md)

For a file download, open the file above and select **Download raw file** on GitHub.

<img src="videos/prompolu-thermal-break/evidence/1080-decoded-final.png" alt="PROMPOLU thermal-break animation final frame: a generic aluminium schematic with polyamide connectors" width="270" />
