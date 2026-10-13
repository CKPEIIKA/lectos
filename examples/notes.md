# Notes for the lectos sample deck

Markdown version of the notes in `slides.tex`. Present with `lectos slides.pdf notes.md`.
Text before the first marker belongs to no slide.

<!-- slide: 1 -->
## Welcome

This deck is about the tool that is presenting it. The slides are a plain PDF; these notes are
a Markdown file with `<!-- slide: N -->` markers.

<!-- slide: 2 -->
## What lectos is

Two windows, one process, all GTK4:

- the projector shows only the slide
- the console shows the current slide, what the audience sees, and the next slide

It does **not** compile anything: build your PDF the way you always do.

<!-- slide: 3 -->
## Notes with mathematics

Equations are typeset with LaTeX and shown as images, for example $\partial_t U + \nabla\cdot F(U) = S(U)$
inline, or the Roe flux as a display equation:

$$\hat F = \frac{F_L+F_R}{2} - \frac12 \lvert\tilde A\rvert\,(U_R-U_L).$$

If a formula does not compile it stays visible as raw TeX.

<!-- slide: 4 -->
## Moving around

Vim keys are optional; arrows and Space always work. Try `o` for the overview and `/` for search: type *Roe*.

<!-- slide: 5 -->
## Freeze and blackout

Freeze to look ahead without the audience seeing it. Unfreezing jumps the projector to the slide you are viewing.

<!-- slide: 6 -->
## Timer and recovery

Pace estimate: elapsed time divided by slides shown, times slides remaining. State is one small JSON file
under `~/.local/state/lectos`.

<!-- slide: 7 -->
## Draw on the slide

Ink is per slide and only kept in memory for now. Roadmap: laser pointer, persistent ink, chalkboard.

<!-- slide: 8 -->
## Try it

Thank you.
