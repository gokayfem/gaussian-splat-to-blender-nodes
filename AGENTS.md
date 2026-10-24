# Repository instructions

Read `skills/gaussian-splat-to-blender-nodes/SKILL.md` before changing the workflow.

For a new reconstruction, start with the [project-agnostic prompting guide](prompts/README.md).
It links the complete project brief, source capture/calibration, part contracts, detail pass,
visual review and delivery prompts. These are reusable project templates, not instructions
to resume the historical Garden job or to launch agents/automations implicitly.

- `skills/gaussian-splat-to-blender-nodes/`: portable skill, scripts and starter.
- `prompts/README.md`: user-facing prompt sequence; canonical templates ship inside the skill.
- `prompts/garden/`: experimental builder, parameters and pinned nodekit.
- `gallery/`: small native examples with explicit artifact versions.
- `tests/`: Python tests and Blender integration instructions.

Run `python3 -m unittest discover -s tests -v` and `python3 tests/check_repository.py`.
For Blender changes, build/audit the starter with `--python-exit-code 1`. For Garden changes,
build affected parts and an integrated checkpoint as needed. Serialize heavy renders and
inspect images after appearance changes. Exit codes and geometry counts do not prove fidelity.

Use deterministic seeds, units and meaningful controls. Keep live generating GN on empty
hosts and Shader Node materials in procedural mode. For an explicitly requested hybrid,
follow the hybrid-projection guide: preserve the source and label mapped surfaces as baked
copies requiring rebakes. Do not apply the live-host audit to them. Never replace beauty
with splats, image planes or an imported scan. Audit reference removal in a disposable process, never an unsaved UI scene.

Keep scans, decoded arrays, blends, videos, credentials and private/session logs untracked.
Check all staged files. Preserve attribution; isolate vendor changes and prefer the local
compatibility adapter. Do not claim a Blender version was tested without running it.

No generation API jobs, agent messages or recurring reviews without user authorization.
Honor user stops. Do not use HyperFrames. Keep plugin/marketplace/skill names consistent.
