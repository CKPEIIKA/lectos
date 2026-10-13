lectos(1) "lectos 0.1.0" "General Commands Manual"

# NAME

lectos - presenter console and projector for PDF slides with Markdown or Beamer notes

# SYNOPSIS

*lectos* [_OPTIONS_] [_PDF_|_FOLDER_] [_NOTES_]++
*lectos-tui* [_OPTIONS_] _PDF_|_FOLDER_ [_NOTES_]

# DESCRIPTION

*lectos* shows your slides (a compiled PDF) to the audience in a projector window and gives you a presenter
console: the current, projected and next slide, your notes, a timer with your standing against the plan, an overview
grid, search, freeze and blackout for the projector, a chalkboard, ink, and a laser pointer.

Without arguments *lectos* opens a window to choose the slides, the notes and folders. Given only the PDF it uses the
notes next to it (_slides.tex_, _slides.md_, else _notes.tex_, _notes.md_); given a folder it uses the PDF in it.

_NOTES_ is a Markdown file (sections tied to slides with *<!-- slide: N -->* markers, LaTeX math between *$* signs) or
a Beamer *.tex* file, whose *\\note{}* commands become the notes. *lectos* never compiles anything: build the PDF
yourself.

The console and the projector are chosen independently. The console is *gtk* (libadwaita) or *tui* (terminal); the
projector is *gtk* (a window of its own, which supports blackout, chalkboard, ink and laser), *zathura* (a Zathura window
driven over D-Bus) or *none*. *lectos-tui* starts the terminal console with Zathura and needs no GTK.

# OPTIONS

*--console* _gtk_|_tui_
	Presenter interface. Default: *gtk*, or *console* under *[ui]* in the options file.

*--projector* _gtk_|_zathura_|_none_
	Audience window. Default: *gtk* (*zathura* for *lectos-tui*), or *projector* under *[ui]*.

*--layout* _auto_|_compact_|_wide_|_draw_
	GTK console layout: for a notebook, for a big screen (adds a filmstrip of previous and upcoming slides), chosen by
	window width, or the quick drawing layout (large slide, drawing toolbar).

*--notes-pages* _auto_|_none_|_left_|_right_
	Where Beamer's second-screen notes (*\\setbeameroption{show notes on second screen}*) sit on each PDF page. With *auto* a
	page much wider than a slide is taken as slide plus notes, notes on the right. The audience sees only the slide half
	with the GTK projector.

*--lang* _auto_|_en_|_ru_|_de_
	Interface language. Default: from *LC_ALL*, *LANGUAGE*, *LANG*.

*--windowed*
	Keep the GTK projector window windowed. It is fullscreen on the last monitor when there are several.

*--monitor* _N_
	Monitor index for the GTK projector window.

*--fullscreen*
	Start the projector fullscreen.

*--no-vim*
	Start with vim keys off (GTK console).

*--config* _FILE_
	Options file. Default: *$XDG_CONFIG_HOME/lectos/options.toml*.

*--version*, *-h*, *--help*
	Print the version or the usage.

# KEYS

Arrows, Space, Page Up/Down, Home and End always navigate. Vim keys are on by default in the GTK console and always on
in the terminal console:

*l*, *h*
	next, previous slide (a count works: *5l*)

*gg*, *G*, *12G*, *:12*
	first, last, slide 12

*j*, *k*
	scroll the notes

*:*
	command line; Tab completes. *:help* lists every command, *?* opens the same list.

*/*, *n*, *N*
	search slides and notes, next and previous hit

*o*, *z*, *b*, *B*, *p*, *t*
	overview, freeze, blackout, chalkboard, laser pointer, timer

*f*, *F*
	projector fullscreen, console fullscreen

*s*, *E*, *S*
	quick drawing layout, edit this slide's notes, settings window

Every button and menu entry is also a command, for example *:target 1h30*, *:color red*, *:clear-all*, *:export*, *:panel strip off*, *:export-ink*.

# FILES

_$XDG_CONFIG_HOME/lectos/options.toml_
	Options: blackout screen, console and header contents, drawing and laser defaults, language. See the example in the
	source tree.

_$XDG_STATE_HOME/lectos/_
	Per-presentation recovery state (current slide, timer, layout, hidden panels) and ink, as small JSON files, and
	notes you edited for a Beamer deck (the _.tex_ itself is never changed).

_$XDG_CACHE_HOME/lectos/math/_
	Cached formula images.

# ENVIRONMENT

*LC_ALL*, *LC_MESSAGES*, *LANGUAGE*, *LANG*
	Select the interface language.

*XDG_CONFIG_HOME*, *XDG_STATE_HOME*, *XDG_CACHE_HOME*
	Where the files above live (defaults under *~/.config*, *~/.local/state*, *~/.cache*).

# EXAMPLES

Present with Beamer notes, GTK console and projector:

```
lectos slides.pdf slides.tex
```

Terminal console with a Zathura projector, Markdown notes:

```
lectos-tui slides.pdf notes.md
```

# EXIT STATUS

0 on a normal exit, 1 when a viewer, a poppler tool or LaTeX fails, 2 for bad arguments or options.

# SEE ALSO

*zathura*(1), *pdftoppm*(1), *pdftotext*(1), *chafa*(1), *latex*(1), *dvipng*(1)

# LICENSE

GNU General Public License, version 3 only. This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.
