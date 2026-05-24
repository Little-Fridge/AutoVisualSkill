# Mock multimodal chat export: Mira slide review style

This synthetic chat export represents a colleague-style multimodal history. The goal is to generate a visual skill for the person Mira: how she critiques slides, marks local regions, and turns generic AI-looking drafts into a cleaner visual argument. Do not infer private attributes; treat Mira as a style profile label.

## Friday thread
Alex: I made a first draft for the launch slide. It still feels very AI-ish. What would you change visually?

Attachment: `source/mira_chat_thread_review.png`

Mira: I would not start by rewriting the copy. First mark the regions that create the AI look: banner weight, boxed fragments, generic arrows, and footer noise. Then redraw around one visual argument.

Mira: Rule of thumb: fewer containers, one clear claim line, and one diagram that actually carries evidence. Orange is allowed only where the viewer should look first.

## Monday follow-up
Attachment: `source/mira_chat_thread_revision.png`

Mira: The approved version is not prettier decoration; it changes what the eye reads first. Keep these visual habits around when revising other decks.

## Task for AutoVisualSkill
Generate an interleaved visual colleague skill that binds Mira's written review habits to the visual evidence in the chat attachments. The output should help an agent critique and redraw new slides in Mira's region-marked style.
