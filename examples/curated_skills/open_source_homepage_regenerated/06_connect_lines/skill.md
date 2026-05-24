# Incremental Line Tracing with Runtime Path Overlay

## Description
This skill traces lines, paths, wires, or maze-like strokes by using a dynamic visual prior. After each local tracing decision, the executor renders the already-traced trajectory, current endpoint, and unresolved branches directly onto the original task image. The next step is performed on that overlay image so trajectory state is visible instead of hidden in conversation memory.

This skill is designed for tasks where the challenge is not recognizing a static symbol, but maintaining an auditable path state across multiple local visual decisions.

## Declarative Textual Logic
- The task is path tracing over visible connected strokes in an image.
- Start from the instructed endpoint, seed point, or visually marked start node.
- At each step, inspect only the local neighborhood around the current endpoint.
- Continue along the visible connected stroke segment that belongs to the same path.
- Do not jump across gaps unless the task explicitly says broken strokes should be bridged.
- When multiple connected continuations are possible, mark them as unresolved branch candidates and choose only after a local visual decision.
- After each accepted segment, render the traced trajectory and current endpoint back onto the original task image.
- Use the latest overlay image for the next step so the traced path is explicit and the executor can avoid loops, reversals, and repeated segments.
- Stop when the target endpoint is reached, the path exits the searchable region, or no connected untraced segment remains.

## Dynamic Visual Priors
This skill uses a **dynamic visual prior** rather than a static prior image.

At runtime, the executor should render an overlay on top of the original task image with the following semantics:
- **Highlighted stroke or polyline** = the trajectory already traced.
- **Current endpoint marker** = the active frontier for the next local decision.
- **Candidate markers** = unresolved branch continuations that must be inspected before committing.
- **Rejected branch marker** = a continuation that was inspected and ruled out.
- **Target marker** = the endpoint or destination when the task provides one.

Renderer requirements:
- The overlay must be drawn onto the current task image, not onto a schematic template.
- Keep path marks thin enough that the underlying stroke remains visible.
- Keep endpoint and branch markers compact and local.
- Do not write long instructions, final answers, or hidden hints into the rendered image.
- Do not pre-render a fixed route; only render state produced during the current run.

## Multimodal Binding Protocol
- **Task input image**: the source image containing the path, line, wire, or maze-like stroke.
- **Dynamic overlay image**: the same task image with traced path state rendered onto it for the next local decision.
- **Coordinate system**: use image coordinates with origin at the top-left.
  - Allowed representations: pixel `(x, y)` or normalized `(x, y)`.
  - One representation must be used consistently throughout a run.
  - The final output must explicitly state `coord_type` for all reported points.
- **Text-to-visual binding**:
  - A rendered path mark means “this segment has already been accepted as part of the trace.”
  - A current endpoint marker means “continue from this local frontier.”
  - Candidate markers mean “these branch continuations are pending local inspection.”
  - Rejected branch markers mean “this continuation was considered but is not part of the active trace.”
- **Search binding rule**: each new step must inspect the latest overlay image so already-traced segments and branch decisions are visible.
- **Never copy from a prior example**:
  - Do not import fixed coordinates, path shapes, or node layouts from another task.
  - Do not treat overlay marks as ground truth independent of the current task image.
  - Do not encode task answers or route identities inside the overlay.

## Runtime Protocol
This is an **iterative** skill.

### State Schema
```json
{
  "round_index": 0,
  "trace_points": [
    {
      "x": 0,
      "y": 0,
      "coord_type": "pixel"
    }
  ],
  "current_endpoint": {
    "x": 0,
    "y": 0,
    "coord_type": "pixel"
  },
  "accepted_segments": [
    {
      "from": [0, 0],
      "to": [0, 0],
      "coord_type": "pixel",
      "round_added": 1
    }
  ],
  "branch_candidates": [
    {
      "id": "b1",
      "x": 0,
      "y": 0,
      "coord_type": "pixel",
      "status": "pending"
    }
  ],
  "stop_reason": ""
}
```

### Update Rule
At round `r`:
1. Render the overlay from all accepted segments, current endpoint, and branch decisions through round `r-1`.
2. Inspect the local neighborhood around the current endpoint in the overlay image.
3. Identify visible connected untraced continuations.
4. If exactly one continuation is locally valid, accept it as the next segment.
5. If multiple continuations are plausible, record branch candidates and inspect local evidence before accepting one.
6. Append the accepted segment to `accepted_segments` and append its endpoint to `trace_points`.
7. Update `current_endpoint` to the new endpoint.
8. Re-render the overlay on the original task image for the next round.

### Renderer Behavior
Renderer name: `iterative_line_trace_overlay`

Inputs:
- base task image
- accepted segment list or trace point polyline
- current endpoint coordinate
- optional branch candidate list
- optional rejected branch list
- optional target endpoint
- line and marker style configuration
- coordinate mode

Outputs:
- overlay image with rendered traced path state
- optional machine-readable render manifest

Behavior:
- Draw the accepted trace as a thin high-contrast path over the source image.
- Draw one compact marker at the current endpoint.
- Draw compact markers for pending and rejected branches when branch bookkeeping exists.
- Preserve the base image content except for minimal path-state annotations.
- Avoid large opaque elements that hide nearby path segments.

### Stop Condition
Stop when one of the following holds:
- the current endpoint reaches the requested target endpoint;
- no connected untraced continuation remains;
- all branch candidates are rejected;
- `max_rounds` is reached.

## Parameters
| Name | Type | Description |
|---|---|---|
| `task_image` | image | Source image containing the path, line, wire, or maze-like stroke. |
| `start_point` | point | Starting endpoint or seed point in pixel or normalized coordinates. |
| `target_point` | point | Optional target endpoint to reach. |
| `coordinate_mode` | string | Coordinate representation: `pixel` or `normalized`. |
| `max_rounds` | integer | Maximum number of trace-and-render rounds before forced stop. |
| `branch_policy` | string | Rule for resolving ambiguous branches, such as follow same color, follow same stroke width, or choose locally connected continuation. |

## Execution Steps
1. Receive the `task_image`, `start_point`, and optional `target_point`.
2. Choose and record a consistent `coordinate_mode`.
3. Initialize state with:
   - `round_index = 0`
   - `trace_points = [start_point]`
   - `current_endpoint = start_point`
   - empty `accepted_segments`
   - empty `branch_candidates`
4. Inspect the local neighborhood around `current_endpoint`.
5. Identify connected untraced continuations that are visually part of the same stroke or path.
6. If one continuation is valid, choose a short next segment and record its endpoint.
7. If several continuations are valid, mark them as branch candidates, apply `branch_policy`, and record unresolved or rejected candidates.
8. Append the accepted segment and update `current_endpoint`.
9. Render all accepted trace state onto the original task image.
10. Increment `round_index` and inspect the new overlay image.
11. Repeat local inspection, segment acceptance, branch bookkeeping, and re-rendering.
12. Stop when the target is reached, no connected untraced continuation remains, or `max_rounds` is reached.
13. Return the final traced path and the auditable branch history.

## Usage Constraints
- Use this skill only when the task requires following visible connected strokes, paths, wires, contours, or maze routes.
- Do not use it to infer invisible paths behind occluders unless the task explicitly allows that.
- Do not jump across disconnected marks unless the task defines the gap as bridgeable.
- Keep overlay marks small and thin enough to preserve the original stroke evidence.
- Do not pre-render fixed coordinates, expected answers, or route templates.
- Keep route semantics in text and runtime state; keep the overlay limited to path-state annotations.
- If the image is cropped or tiled during execution, reconcile coordinates back to the original image frame.

## Output Format
Return JSON with enough intermediate state to audit the iterative dynamic prior.

```json
{
  "status": "CONTINUE|DONE|BLOCKED",
  "trace_points": [
    {
      "x": 0,
      "y": 0,
      "coord_type": "pixel|normalized"
    }
  ],
  "current_endpoint": {
    "x": 0,
    "y": 0,
    "coord_type": "pixel|normalized"
  },
  "accepted_segments": [
    {
      "from": [0, 0],
      "to": [0, 0],
      "coord_type": "pixel|normalized",
      "round_added": 1
    }
  ],
  "branch_candidates": [
    {
      "id": "b1",
      "x": 0,
      "y": 0,
      "coord_type": "pixel|normalized",
      "status": "pending|accepted|rejected"
    }
  ],
  "rounds": 0,
  "stop_reason": "target_reached|no_connected_segment|max_rounds_reached|blocked",
  "rendered_overlay_path": "optional path to latest overlay image"
}
```

Requirements:
- `trace_points` must describe the accepted trajectory in order.
- `current_endpoint` must match the final point in `trace_points` unless the run is blocked before a valid update.
- `accepted_segments` must be consistent with `trace_points`.
- `branch_candidates` should preserve pending, accepted, and rejected branch decisions when branches were encountered.
- Use one coordinate convention consistently and declare it for every point via `coord_type`.
