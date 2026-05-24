# Source Notes

This showcase uses the public ARC-AGI-3 `ls20` environment through the official
`arc-agi` Python toolkit.

- `assets/arc_ls20_source_frame.png`: screened intermediate frame rendered from
  the public ARC-AGI-3 `ls20-9607627b` environment on 2026-05-29. The frame is
  reached by the original action prefix `ACTION3, ACTION3, ACTION3, ACTION1`.
- `assets/arc_ls20_route_state_overlay.png`: the same run after a short local
  action sequence, with dynamic route-state marks rendered onto the current
  frame.
- `assets/arc_ls20_route_state_demo.gif`: animated without/with comparison for
  the same official episode. Both branches share the prefix, then the direct
  branch takes `ACTION2` / down while the visual-skill branch takes `ACTION1` /
  up and continues along the official route.
- `assets/arc_ls20_runtime_trace.png`: static final preview contrasting the
  direct off-route branch with the completed visual-skill route.

The frame is generated from the public ARC-AGI-3 environment. The visual overlay
is a curated AutoVisualSkill-compatible dynamic renderer demonstration: it
shows how a generated dynamic skill should externalize state during an
interactive ARC episode. It is not presented as a full ARC solution or as a
scorecard result.

Downstream action check:

- Official next action for this original frame: `ACTION1` / up.
- Gemini direct run on the raw frame chose `ACTION2` / down.
- Gemini with the generated visual skill and route-state overlay chose
  `ACTION1` / up.

Official route rendered in the animation:

```text
ACTION3, ACTION3, ACTION3, ACTION1, ACTION1, ACTION1, ACTION1,
ACTION4, ACTION4, ACTION4, ACTION1, ACTION1, ACTION1
```

The first divergent action is the recorded Gemini comparison. After that branch
point, the visual-skill side plays the official remaining route so the full
route-state protocol is visible, not only the next-action decision.

Generation prompt used for the showcase:

```text
Create a dynamic visual skill for ARC-AGI-3 route-state planning. Use the
provided ARC frame as a concrete source image. The skill should render sparse
runtime marks directly onto each returned frame: current controllable object,
visited route, waypoint target, and next local plan. Avoid long in-image text,
avoid opaque marks, and preserve the original game pixels for the next action.
```
