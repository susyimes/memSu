# memSu V4 Plan: Inspire-Driven Observation

V4 starts by improving `inspire`: the agent should be model-led, but the model
needs a stronger observation contract than a loose prompt.

## Goal

Turn inspire notes into a user-owned observation guide that improves recall,
evidence quality, and tool/source coverage without hard-coding personal absolute
paths.

## Principles

- Write directions, not fixed path lists.
- Let the model discover concrete paths at run time from local evidence.
- Make changes first-class: new, removed, active, stale, or unknown.
- Separate facts, inferences, unknowns, and suggestions.
- Require evidence for important claims.
- Keep memory candidate creation review-first.

## Minimum Signal Surfaces

V4 inspire should remind the observation agent to consider:

- file modification times in common work roots, project roots, downloads,
  desktop items, and build output areas
- Git records for active repositories, including recent log, status, and commit
  stats
- Windows Recent shortcut metadata for recently opened projects, files, tools,
  archives, APKs, images, and directories
- PowerShell history for recent build, ADB, signing, packaging, and agent/tool
  commands
- current processes and window titles for active IDEs, browsers, build tools,
  terminals, and agents
- local agent metadata such as session indexes, titles, update times, and
  summaries, without expanding full private conversations by default
- build and release artifacts such as APKs, zips, protected outputs, market
  packages, and downloaded assets

## Initial Implementation

- `inspire.md` remains the main high-signal user note.
- `inspire.d/*.md` files are read after `inspire.md`, sorted by file name.
- `memsu inspire init` creates starter V4 split notes when missing and does not
  overwrite user edits unless `--force` is used.
- The starter notes define a V4 observation loop, local signal surfaces, output
  contract, and signal-quality rules.

## Next Step

The next V4 step is to make `observe agent` execute bounded read-only probes
against the signal surfaces, then persist a real observation brief instead of
only recording a plan.
