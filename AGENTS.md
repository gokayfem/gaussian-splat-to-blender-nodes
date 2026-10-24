# Repository instructions

Read `skills/gaussian-splat-to-blender-nodes/SKILL.md` before changing the workflow.

- `skills/gaussian-splat-to-blender-nodes/`: portable skill, scripts and starter.
- `prompts/garden/`: experimental builder, parameters and pinned nodekit.
- `gallery/`: small native examples with explicit artifact versions.
- `tests/`: Python tests and Blender integration instructions.

Run `python3 -m unittest discover -s tests -v` and `python3 tests/check_repository.py`.
For Blender changes, build/audit the starter with `--python-exit-code 1`. For Garden changes,
build affected parts and an integrated checkpoint as needed. Serialize heavy renders and
inspect images after appearance changes. Exit codes and geometry counts do not prove fidelity.

Use deterministic seeds, units and meaningful controls. Keep live generating GN on empty
hosts and Shader Node materials. Never replace native beauty with splats, image planes or
an imported scan. Audit reference removal in a disposable process, never an unsaved UI scene.

Keep scans, decoded arrays, blends, videos, credentials and private/session logs untracked.
Check all staged files. Preserve attribution; isolate vendor changes and prefer the local
compatibility adapter. Do not claim a Blender version was tested without running it.

No generation API jobs, agent messages or recurring reviews without user authorization.
Honor user stops. Do not use HyperFrames. Keep plugin/marketplace/skill names consistent.
