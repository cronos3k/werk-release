# Examples for profile `presentation/1`

Everything here is real output: the payload examples are cut from one small deck by the same
code that saves a real one, and the test suite fails if they drift.

The example deck — 960 × 540 points, the application's default master, two slides:

    slide 201  "Quarterly results"     a title placeholder (shape 211); a body placeholder (212)
                                       with a bold run, a bullet, a slide-number field, a line
                                       break and a link to slide 202; a picture (213) showing
                                       media 301; a speaker note; a `fade` transition; one
                                       `fly` entrance animation on shape 212; one comment
    slide 202  "Every kind of shape"   a star with a gradient (221); a group (222) of an
                                       ellipse (223) and a rectangle (224); a connector (225)
                                       glued to the star; a 2 x 2 table (226); a column chart
                                       (227); a media clip (228) playing media 302; ink (229);
                                       a freeform triangle (230); an object kept as XML (231)
    media 301  swatch.png              a 2 x 2 PNG
    media 302  dot.gif                 a 1 x 1 GIF

| file | what it is |
|---|---|
| `document.example.json` | the `core.slide.document` payload: slide order, the master and its layouts, the media table, one section, the default text style |
| `slide.example.json` | the `core.slide.slide` payload of slide 201 |
| `slide-every-kind.example.json` | the `core.slide.slide` payload of slide 202: one shape of every `kind.type` |
| `layout.example.json` | the `core.slide.layout` payload of the layout slide 201 uses (title and content) |
| `master.example.json` | the `core.slide.master` payload: theme, placeholders, text styles |
| `geometry.example.json` | the `core.slide.geometry` payload of slide 202: the star, the ellipse, the rectangles and the line as paths |
| `asset.example.json` | the `core.media.asset` descriptor of media 302 (`encoding` `gif`, `definition` `formats`) |
| `ooxml.example.json` | the `x.deckcraft.ooxml` payload of slide 202: two fragments, each with the pointer of the member it belongs at |
| `outline.example.txt` | the `core.slide.outline` payload of the deck |
| `read_presentation.py` | a complete reader, Python standard library only: `python read_presentation.py <capsule>` |
| `write_minimal.py` | a complete writer of a minimal capsule, standard library only: `python write_minimal.py <existing capsule> <new.werk>` |

To check a reader you are writing: read `slide.example.json` and compare what you find with
the description above, shape by shape; then resolve shape 221 of slide 202 against
`geometry.example.json` (pointer `/slide/shapes/0`) and draw the star. To check a writer:
produce the four payloads of `spec/PROFILE-PRESENTATION.md` section 7.1 and compare sizes and
hashes.
