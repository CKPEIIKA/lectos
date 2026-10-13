lectos-tui(1) "lectos 0.1.0" "General Commands Manual"

# NAME

lectos-tui - terminal presenter console for PDF slides

# SYNOPSIS

*lectos-tui* [_OPTIONS_] _PDF_|_FOLDER_ [_NOTES_]

# DESCRIPTION

*lectos-tui* is *lectos --console tui* with *--projector zathura* as the default. It needs no GTK: the console is a
standard-library terminal interface (notes as styled text, slide previews through *pdftoppm* and *chafa*, Unicode
approximations of math) and the audience sees a Zathura window.

It takes the same options as *lectos*(1), which also describes the keys and the options file. Ink, chalkboard and
blackout are available only with *--projector gtk*; the laser pointer needs the GTK console.

# SEE ALSO

*lectos*(1)

# LICENSE

GNU General Public License, version 3 only.
