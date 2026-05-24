# Dense Object Counting with Iterative Anchor Overlay

## Description
This skill counts many visually similar object instances in a dense image by using an iterative dynamic visual prior. After each counting round, the executor renders a compact anchor mark onto every confirmed counted object directly on the original task image. The next round is performed on that overlay image so already counted instances are explicitly marked and the search can focus on unmarked targets. The process continues until a full scan finds no new confident instances.

This skill is designed for scenes where the main challenge is not just detecting one object, but reliably tracking which instances have already been counted.

## Declarative Textual Logic
- The task is dense repeated-instance counting from an image.
- The counting unit is one individual target instance as defined by the task prompt.
- Do not count clusters, shadows, reflections, repeated texture fragments, or background motifs unless the task explicitly says they are valid targets.
- Use an iterative anchor-and-search loop:
  1. inspect the current image,
  2. find distinct unmarked target instances,
  3. place exactly one canonical anchor per newly confirmed instance,
  4. render all confirmed anchors back onto the original image,
  5. search again for remaining unmarked instances.
- Anchor placement must follow a single canonical rule for the whole task, such as object center, centroid, or a stable visible interior point.
- One confirmed anchor corresponds to exactly one counted object instance.
- Maintain a consistent scan policy across rounds, such as left-to-right then top-to-bottom, region-by-region, or sector-by-sector.
- If the scene is very dense, the image may be mentally partitioned into subregions, but all anchors must be reconciled into one global list.
- When evidence is ambiguous, apply a conservative inclusion rule: if the task does not specify otherwise, count only instances with sufficient visual evidence to support that they are distinct objects.
- Before accepting a new anchor, compare it against existing anchors to avoid recounting the same instance.
- If two anchors appear to refer to the same object, keep one canonical anchor and reject or merge the duplicate.
- Stop when a complete additional scan of the latest overlay yields zero new confident anchors, or when `max_rounds` is reached.
- The final count equals the number of confirmed non-duplicate anchors in the final state.

## Visual Priors
This skill uses a **dynamic visual prior** rather than a static prior image.

At runtime, the executor should render an overlay on top of the original task image with the following semantics:
- **Small solid dot or small cross** at an anchor location = one counted object instance.
- **Color A** = anchors confirmed in prior rounds.
- **Color B** = anchors newly added in the current round before consolidation into the persistent set.
- **Optional thin ring** around an anchor = local duplicate-suppression neighborhood used only as a visual aid to reduce recounting nearby.
- **All unmarked image regions remain visually unchanged** so the scene stays searchable.

Renderer requirements:
- Anchor marks must be compact and minimally occluding.
- The overlay must be drawn onto the original task image, not onto a cropped schematic unless the task explicitly uses tiling as part of execution.
- The overlay must visualize only runtime counting state, not task instructions or answers.
- No long text, class names, expected totals, or dataset-specific hints should appear in the rendered image.

## Multimodal Binding Protocol
- **Task input image**: the source scene containing dense repeated targets.
- **Dynamic overlay image**: the same task image with counted anchors rendered onto it for the next search round.
- **Coordinate system**: use image coordinates with origin at the top-left.
  - Allowed representations: pixel `(x, y)` or normalized `(x, y)`.
  - One representation must be used consistently throughout a run.
  - The final output must explicitly state `coord_type` for every anchor.
- **Text-to-visual binding**:
  - A rendered compact mark means “this instance has already been counted.”
  - Prior-round anchor color means persistent confirmed state.
  - Current-round anchor color means provisional additions from the current scan before final consolidation.
  - An optional ring indicates a local neighborhood where a near-duplicate anchor should be treated with caution.
- **Canonical binding rule**: one anchor = one counted object.
- **Anchor placement rule**: bind anchors to the canonical object point defined by `anchor_rule`, such as center or stable interior point.
- **Search binding rule**: each new round must inspect the overlay image so previously counted objects are visibly marked.
- **Never copy from the prior**:
  - Do not treat any overlay mark as a ground-truth object location independent of the current task image.
  - Do not import fixed layouts, coordinates, or counts from previous tasks.
  - Do not assume any benchmark- or dataset-specific target pattern.
  - Do not encode detailed policy, object definitions, or stop logic inside the overlay itself.

## Runtime Protocol
This is an **iterative** skill.

### State Schema
```json
{
  "round_index": 0,
  "anchors": [
    {
      "id": "a1",
      "x": 0,
      "y": 0,
      "coord_type": "pixel",
      "status": "confirmed",
      "round_added": 1
    }
  ],
  "new_anchor_ids": [],
  "scan_policy": "left-to-right, top-to-bottom",
  "stop_reason": ""
}
```

### Update Rule
At round `r`:
1. Render the overlay from all confirmed anchors through round `r-1` on the original task image.
2. Inspect that overlay using the chosen scan policy.
3. Identify distinct target instances that remain unmarked.
4. For each such instance, place one canonical candidate anchor.
5. Compare each candidate against existing anchors using coordinate proximity and visual identity checks.
6. Accept non-duplicate anchors as `confirmed`, and mark duplicate candidates as `rejected` or `merged` if bookkeeping is retained.
7. Record accepted anchor ids in `new_anchor_ids`.
8. Re-render the overlay using the updated confirmed anchor set.

### Renderer Behavior
Renderer name: `iterative_count_anchor_overlay`

Inputs:
- base task image
- confirmed anchor list with coordinates
- optional list of anchors newly added this round
- anchor style configuration
- coordinate mode

Outputs:
- overlay image with rendered counted anchors
- optional machine-readable render manifest

Behavior:
- Draw one compact mark at every confirmed anchor location.
- Optionally use a distinct style for current-round additions versus prior anchors.
- Preserve the base image content except for minimal anchor marks.
- Avoid large opaque elements that would hide nearby objects.

### Stop Condition
Stop when either:
- a full scan of the latest overlay yields zero new confirmed anchors, or
- `max_rounds` is reached.

## Parameters
| Name | Type | Description |
|---|---|---|
| `task_image` | image | Source image containing many candidate target instances. |
| `target_definition` | string | Text definition of what object category or visual pattern counts as one target instance. |
| `anchor_rule` | string | Canonical anchor placement rule, e.g. center, centroid, or stable visible interior point. |
| `max_rounds` | integer | Maximum number of search-and-render rounds before forced stop. |
| `coordinate_mode` | string | Coordinate representation: `pixel` or `normalized`. |
| `duplicate_radius` | number | Optional duplicate suppression radius relative to object or image scale. |

## Execution Steps
1. Receive the `task_image` and `target_definition`.
2. Determine the counting unit from the task definition and clarify any explicit inclusion or exclusion rules.
3. Choose and fix a canonical `anchor_rule` for the entire run.
4. Choose and record a consistent `scan_policy`.
5. Initialize state with:
   - `round_index = 0`
   - empty `anchors`
   - empty `new_anchor_ids`
   - chosen `scan_policy`
6. Inspect the original task image and identify a batch of distinct target instances not yet marked.
7. For each newly found instance, place one candidate anchor at the canonical object point.
8. Compare each candidate anchor with existing anchors to detect likely duplicates.
9. Confirm non-duplicate anchors, assign unique ids, set `round_added`, and record `coord_type`.
10. Render all confirmed anchors onto the original task image to create the next overlay.
11. Increment `round_index` and inspect the overlay image for remaining unmarked targets.
12. Repeat anchor placement, duplicate checking, confirmation, and re-rendering.
13. If needed for very dense scenes, subdivide the scene into regions during scanning, but keep all accepted anchors in one global coordinate frame.
14. When a complete scan yields no new confident anchors, stop and set `stop_reason` accordingly.
15. Return the final count and the auditable anchor list.

## Usage Constraints
- Use this skill only for true repeated-instance counting or enumeration from imagery.
- Do not use it to infer hidden or fully occluded objects that are not visually supported.
- Do not treat clusters as single objects unless the task explicitly defines the cluster as the counting unit.
- Do not count shadows, reflections, printed icons, or repeated textures unless the task explicitly defines them as targets.
- Keep anchors small relative to object scale whenever possible to reduce occlusion.
- Do not let the dynamic prior become a task-instance template; it is only runtime state for the current image.
- Do not pre-render fixed coordinates, expected totals, or answer-like hints.
- Do not encode dataset-specific object classes, scene identities, or benchmark exemplars into the overlay.
- Do not place multiple anchors on one object unless the task explicitly defines multiple countable subparts.
- If image tiling or regional scanning is used, reconcile overlaps carefully to prevent double counting across boundaries.
- If evidence for distinctness is weak, prefer exclusion over speculative counting unless the task provides a different policy.

## Output Format
Return JSON with enough intermediate state to audit the iterative dynamic prior.

```json
{
  "count": 0,
  "anchors": [
    {
      "id": "a1",
      "x": 0,
      "y": 0,
      "coord_type": "pixel|normalized",
      "status": "confirmed|rejected|merged",
      "round_added": 1
    }
  ],
  "rounds": 0,
  "stop_reason": "no_new_anchors|max_rounds_reached|other",
  "scan_policy": "left-to-right, top-to-bottom",
  "round_history": [
    {
      "round_index": 1,
      "new_anchor_ids": ["a1", "a2"],
      "new_confirmed_count": 2,
      "rejected_or_merged_ids": [],
      "notes": "optional brief audit note"
    }
  ]
}
```

Requirements:
- `count` must equal the number of final non-duplicate confirmed anchors.
- `anchors` must contain one record per audited anchor candidate retained in state.
- For dynamic counting, the `anchors` field is mandatory and must include ids and coordinates for accepted instances.
- `round_history` should make it possible to audit how the dynamic overlay evolved across rounds.
- Use one coordinate convention consistently and declare it in each anchor via `coord_type`.
- If duplicates were detected, preserve their status as `rejected` or `merged` when such bookkeeping is available.
