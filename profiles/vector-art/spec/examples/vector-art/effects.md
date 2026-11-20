# Live effects VectorCraft writes

An effect is `{"id": …, "params": {…}, "visible": bool}` in an `effects` list of an appearance, a fill or a stroke (`spec/PROFILE-VECTOR-ART.md` section 4). The vocabulary is open: draw the object WITHOUT an effect you do not implement, and keep the effect when you write the object back. Lengths are points, angles degrees. A parameter that is absent has the default given here.

Geometry effects change the outline that is painted; raster effects are computed on the painted pixels at the document's `raster_effects_ppi`.

## `threeD.revolve`

Revolve (geometry; menu: Effect › 3D and Materials).

Parameters: {angle: degrees (0..360, 360), offset: pt (0..100000, 0), edge: left|right, rotationX: degrees (0), rotationY: degrees (0), rotationZ: degrees (0), perspective: % (0..100, 0), segments: integer (8..128, 64), shade: bool (true), lightAzimuth: degrees (-45), lightElevation: degrees (45), lightIntensity: % (80), ambient: % (25), expandVisibleOnly: bool (true, trim covered opaque solid surfaces only on Expand Appearance)}. Open paths create uncapped surfaces; intersecting profiles use approximate painter visibility.

Defaults: `{"ambient":25.0,"angle":360.0,"edge":"left","expandVisibleOnly":true,"lightAzimuth":-45.0,"lightElevation":45.0,"lightIntensity":80.0,"offset":0.0,"perspective":0.0,"rotationX":0.0,"rotationY":0.0,"rotationZ":0.0,"segments":64,"shade":true}`

## `convertToShape.rectangle`

Rectangle (geometry; menu: Effect › Convert to Shape).

Parameters: {relative: bool (true), extraW: pt (18), extraH: pt (18), width: pt (absolute, 100), height: pt (absolute, 100)}

Defaults: `{"extraH":18.0,"extraW":18.0,"height":100.0,"relative":true,"width":100.0}`

## `convertToShape.roundedRectangle`

Rounded Rectangle (geometry; menu: Effect › Convert to Shape).

Parameters: {relative: bool (true), extraW: pt (18), extraH: pt (18), width, height (absolute), radius: pt (9)}

Defaults: `{"extraH":18.0,"extraW":18.0,"height":100.0,"radius":9.0,"relative":true,"width":100.0}`

## `convertToShape.ellipse`

Ellipse (geometry; menu: Effect › Convert to Shape).

Parameters: {relative: bool (true), extraW: pt (18), extraH: pt (18), width, height (absolute)}

Defaults: `{"extraH":18.0,"extraW":18.0,"height":100.0,"relative":true,"width":100.0}`

## `distort.freeDistort`

Free Distort (geometry; menu: Effect › Distort & Transform).

Parameters: {corners: [[x,y]×4] new positions of the bounding-box corners TL, TR, BR, BL in unit box coordinates (identity [[0,0],[1,0],[1,1],[0,1]])}

Defaults: `{"corners":[[0.0,0.0],[1.0,0.0],[1.0,1.0],[0.0,1.0]]}`

## `distort.puckerBloat`

Pucker & Bloat (geometry; menu: Effect › Distort & Transform).

Parameters: {amount: % (-200 pucker … 200 bloat, default 0)}

Defaults: `{"amount":0.0}`

## `distort.roughen`

Roughen (geometry; menu: Effect › Distort & Transform).

Parameters: {size: 0..100 (5), relative: bool (true: % of size; false: pt), detail: per inch 0..100 (10), points: "smooth"|"corner", seed: int (0)}

Defaults: `{"detail":10.0,"points":"smooth","relative":true,"seed":0,"size":5.0}`

## `distort.transform`

Transform (geometry; menu: Effect › Distort & Transform).

Parameters: {scaleH: % (100), scaleV: % (100), moveH: pt (0; right = +), moveV: pt (0; down = +), rotate: deg (0; counter-clockwise), copies: 0..1000 (0; each copy transforms the last again), reflectX: bool (false; flips left to right), reflectY: bool (false; flips top to bottom), reference: 0..8 (4; the point of the bounds' 9-point grid it scales, rotates and reflects about: 0 top left, 4 centre, 8 bottom right), random: bool (false; each scale goes a random share of the way from 100 % to its value, each move and the angle a random share of theirs, differently for each object and the same on every redraw)}

Defaults: `{"copies":0,"moveH":0.0,"moveV":0.0,"random":false,"reference":4,"reflectX":false,"reflectY":false,"rotate":0.0,"scaleH":100.0,"scaleV":100.0}`

## `distort.tweak`

Tweak (geometry; menu: Effect › Distort & Transform).

Parameters: {h: amount (10), v: amount (10), relative: bool (true: % of size), anchors: bool (true), in: bool (true), out: bool (true), seed: int (0)}

Defaults: `{"anchors":true,"h":10.0,"in":true,"out":true,"relative":true,"seed":0,"v":10.0}`

## `distort.twist`

Twist (geometry; menu: Effect › Distort & Transform).

Parameters: {angle: deg (-3600..3600, 10)}

Defaults: `{"angle":10.0}`

## `distort.zigZag`

Zig Zag (geometry; menu: Effect › Distort & Transform).

Parameters: {size: (10), relative: bool (false: pt; true: % of size), ridges: per segment 0..100 (4), points: "smooth"|"corner"}

Defaults: `{"points":"smooth","relative":false,"ridges":4,"size":10.0}`

## `path.offsetPath`

Offset Path (geometry; menu: Effect › Path).

Parameters: {offset: pt (10; negative insets), joins: "miter"|"round"|"bevel", miterLimit: (4)}

Defaults: `{"joins":"miter","miterLimit":4.0,"offset":10.0}`

## `path.outlineStroke`

Outline Stroke (geometry; menu: Effect › Path).

Parameters: {width?: pt (defaults to the stroke's weight)} the outline of the stroke the effect is on (on a fill or the object: the top stroke), with its caps, joins, dashes, alignment, width profile and arrowheads

Defaults: `{}`

## `stylize.roundCorners`

Round Corners (geometry; menu: Effect › Stylize).

Parameters: {radius: pt (10)}

Defaults: `{"radius":10.0}`

## `stylize.scribble`

Scribble (geometry; menu: Effect › Stylize).

Parameters: {angle: deg (30), overlap: pt (0), strokeWidth: pt (3), curviness: % (5), spacing: pt (5), variation: pt (0.5), seed: int (0)} (simplified: a single hatching scribble outlined to a filled shape)

Defaults: `{"angle":30.0,"curviness":5.0,"overlap":0.0,"seed":0,"spacing":5.0,"strokeWidth":3.0,"variation":0.5}`

## `stylize.dropShadow`

Drop Shadow (raster; menu: Effect › Stylize).

Parameters: {mode: blend mode ("multiply"), opacity: % (75), x: pt (7), y: pt (7), blur: pt (5), color: "#rrggbb" ("#000000")}

Defaults: `{"blur":5.0,"color":"#000000","mode":"multiply","opacity":75.0,"x":7.0,"y":7.0}`

## `stylize.innerGlow`

Inner Glow (raster; menu: Effect › Stylize).

Parameters: {mode: blend mode ("screen"), opacity: % (75), blur: pt (5), color: "#rrggbb" ("#ffffff"), source: "center"|"edge" ("edge")}

Defaults: `{"blur":5.0,"color":"#ffffff","mode":"screen","opacity":75.0,"source":"edge"}`

## `stylize.outerGlow`

Outer Glow (raster; menu: Effect › Stylize).

Parameters: {mode: blend mode ("screen"), opacity: % (75), blur: pt (5), color: "#rrggbb" ("#ffff00")}

Defaults: `{"blur":5.0,"color":"#ffff00","mode":"screen","opacity":75.0}`

## `stylize.feather`

Feather (raster; menu: Effect › Stylize).

Parameters: {radius: pt (5)}

Defaults: `{"radius":5.0}`

## `blur.gaussian`

Gaussian Blur (raster; menu: Effect › Blur).

Parameters: {radius: pt (5)}

Defaults: `{"radius":5.0}`

## `artistic.filmGrain`

Film Grain (raster; menu: Effect › Artistic).

Parameters: {grain: 0..20 (4; monochrome noise in shadows and midtones), highlightArea: 0..20 (0; widens the bright highlight area), intensity: 0..10 (10; highlight strength and quieter highlight grain)}. Smooth document-space grain follows translations; minification uses approximate footprint filtering. Coverage and pure white are preserved; black takes light speckles, and saturated colour channels may clip. Grain 0 with either highlightArea 0 or intensity 0 leaves the art unchanged. Original visual approximation; chosen VectorCraft defaults.

Defaults: `{"grain":4.0,"highlightArea":0.0,"intensity":10.0}`

## `blur.radial`

Radial Blur (raster; menu: Effect › Blur).

Parameters: {amount: 1..100 (10; spin: an arc of `amount`°, zoom: the content scaled by up to about ±amount/2 %), method: "spin"|"zoom" ("spin"), quality: "draft"|"good"|"best" ("good"; 16, 64 or 256 samples)} blurs around the object's centre

Defaults: `{"amount":10.0,"method":"spin","quality":"good"}`

## `blur.smart`

Smart Blur (raster; menu: Effect › Blur).

Parameters: {radius: pt 0.1..100 (3), threshold: levels 0.1..100 (25; only colours closer than this blur together, so edges stay sharp), quality: "low"|"medium"|"high" ("medium"; 5, 7 or 9 samples across)} (Normal mode)

Defaults: `{"quality":"medium","radius":3.0,"threshold":25.0}`

## `brushStrokes.accentedEdges`

Accented Edges (raster; menu: Effect › Brush Strokes).

Parameters: {edgeWidth: pt 1..14 (2), edgeBrightness: 0..50 (38; high: white chalk, low: black ink), smoothness: 1..15 (5; softens the object first and leaves its faint edges out)} accentuates the object's edges

Defaults: `{"edgeBrightness":38.0,"edgeWidth":2.0,"smoothness":5.0}`

## `brushStrokes.angledStrokes`

Angled Strokes (raster; menu: Effect › Brush Strokes).

Parameters: {directionBalance: 0..100 (50; 0: every stroke a left diagonal, 100: every stroke a right diagonal, between: light areas right, dark areas left), strokeLength: pt 3..50 (15), sharpness: 0..10 (3)} repaints the object with diagonal strokes, the light areas' going the opposite way to the dark areas'

Defaults: `{"directionBalance":50.0,"sharpness":3.0,"strokeLength":15.0}`

## `brushStrokes.crosshatch`

Crosshatch (raster; menu: Effect › Brush Strokes).

Parameters: {strokeLength: pt 3..50 (9), sharpness: 0..20 (6), strength: 1..3 (1; passes of hatching)} keeps the object's detail under pencil hatching along both diagonals and roughens its edges

Defaults: `{"sharpness":6.0,"strength":1.0,"strokeLength":9.0}`

## `brushStrokes.darkStrokes`

Dark Strokes (raster; menu: Effect › Brush Strokes).

Parameters: {balance: 0..10 (5; the higher, the more of the object counts as dark), blackIntensity: 0..10 (6), whiteIntensity: 0..10 (2)} paints the dark areas closer to black with short strokes and the light areas with long white strokes

Defaults: `{"balance":5.0,"blackIntensity":6.0,"whiteIntensity":2.0}`

## `brushStrokes.inkOutlines`

Ink Outlines (raster; menu: Effect › Brush Strokes).

Parameters: {strokeLength: pt 1..50 (4), darkIntensity: 0..50 (20), lightIntensity: 0..50 (10)} redraws the object in pen and ink: fine outlines over its edges and ink strokes in its shadows

Defaults: `{"darkIntensity":20.0,"lightIntensity":10.0,"strokeLength":4.0}`

## `brushStrokes.spatter`

Spatter (raster; menu: Effect › Brush Strokes).

Parameters: {sprayRadius: pt 0..25 (10; colours scattered up to 0.4 × this), smoothness: 1..15 (5; larger, smoother grains)} renders the object as if sprayed with a spatter airbrush

Defaults: `{"smoothness":5.0,"sprayRadius":10.0}`

## `brushStrokes.sprayedStrokes`

Sprayed Strokes (raster; menu: Effect › Brush Strokes).

Parameters: {strokeLength: pt 0..20 (12), sprayRadius: pt 0..25 (7; strokes scattered up to 0.3 × this), strokeDirection: "rightDiagonal"|"horizontal"|"leftDiagonal"|"vertical" ("rightDiagonal")} repaints the object with sprayed, angled strokes of its main colours

Defaults: `{"sprayRadius":7.0,"strokeDirection":"rightDiagonal","strokeLength":12.0}`

## `brushStrokes.sumiE`

Sumi-e (raster; menu: Effect › Brush Strokes).

Parameters: {strokeWidth: pt 3..15 (10), strokePressure: 0..15 (2; more ink), contrast: 0..40 (16)} paints the object in the Japanese style, as if with a wet brush full of black ink on rice paper: soft, blurred edges and rich blacks, the colours keeping their hue and the object its shape

Defaults: `{"contrast":16.0,"strokePressure":2.0,"strokeWidth":10.0}`

## `distort.diffuseGlow`

Diffuse Glow (raster; menu: Effect › Distort).

Parameters: {graininess: 0..10 (6; white grain, thicker in the glow), glowAmount: 0..20 (10), clearAmount: 0..20 (15; the higher, the more of the image stays clear of glow)} renders the object as if seen through a soft diffusion filter: its highlights glow white under see-through white grain

Defaults: `{"clearAmount":15.0,"glowAmount":10.0,"graininess":6.0}`

## `distort.glass`

Glass (raster; menu: Effect › Distort).

Parameters: {distortion: 0..20 (5), smoothness: 1..15 (3), texture: "blocks"|"canvas"|"frosted"|"tinyLens" ("frosted"; surfaces made in code), scaling: % 50..200 (100), invert: bool (false; turns the surface's heights over)} makes the object look as if seen through glass

Defaults: `{"distortion":5.0,"invert":false,"scaling":100.0,"smoothness":3.0,"texture":"frosted"}`

## `distort.oceanRipple`

Ocean Ripple (raster; menu: Effect › Distort).

Parameters: {rippleSize: 1..15 (9), rippleMagnitude: 0..20 (9)} adds randomly spaced ripples, as if the object were under water

Defaults: `{"rippleMagnitude":9.0,"rippleSize":9.0}`

## `sharpen.unsharpMask`

Unsharp Mask (raster; menu: Effect › Sharpen).

Parameters: {amount: % 1..500 (50), radius: pt 0.1..250 (1; σ of the blur edges are found against), threshold: levels 0..255 (0; smaller differences are left alone)}

Defaults: `{"amount":50.0,"radius":1.0,"threshold":0.0}`

## `stylize.glowingEdges`

Glowing Edges (raster; menu: Effect › Stylize).

Parameters: {edgeWidth: pt 1..14 (2), edgeBrightness: 0..20 (6), smoothness: pt 1..15 (5)} finds alpha-weighted Sobel edges and draws bright coloured outlines on black

Defaults: `{"edgeBrightness":6.0,"edgeWidth":2.0,"smoothness":5.0}`

## `pixelate.colorHalftone`

Color Halftone (raster; menu: Effect › Pixelate).

Parameters: {maxRadius: pt 4..127 (8; the radius of a dot at full strength, which fills its square cell), channel1: screen angle deg -360..360 (108), channel2: deg (162), channel3: deg (90), channel4: deg (45)} screens each colour channel (red, green, blue: channels 1 to 3; in CMYK documents cyan, magenta, yellow, black: 1 to 4) at its angle into dots whose area follows the channel's mean over their cell

Defaults: `{"channel1":108.0,"channel2":162.0,"channel3":90.0,"channel4":45.0,"maxRadius":8.0}`

## `pixelate.crystallize`

Crystallize (raster; menu: Effect › Pixelate).

Parameters: {cellSize: pt 3..300 (10)} redraws the object as polygon crystals of solid colour around random points about cellSize apart

Defaults: `{"cellSize":10.0}`

## `pixelate.mezzotint`

Mezzotint (raster; menu: Effect › Pixelate).

Parameters: {type: "fineDots"|"mediumDots"|"grainyDots"|"coarseDots"|"shortLines"|"mediumLines"|"longLines"|"shortStrokes"|"mediumStrokes"|"longStrokes" ("fineDots")} turns each colour channel fully on or off against a random pattern of dots, lines or strokes: fully saturated colours

Defaults: `{"type":"fineDots"}`

## `pixelate.pointillize`

Pointillize (raster; menu: Effect › Pixelate).

Parameters: {cellSize: pt 3..300 (5)} redraws the object as randomly placed dots of its colours on a white canvas

Defaults: `{"cellSize":5.0}`

## `texture.craquelure`

Craquelure (raster; menu: Effect › Texture).

Parameters: {crackSpacing: pt 2..100 (15; how far apart the cracks are), crackDepth: 0..10 (6; how deep and wide the cracks are, and how high the plates and the tones stand), crackBrightness: 0..10 (9; how brightly the plaster is lit)} paints the object on relief plaster cracked into plates and along the contours of its tones

Defaults: `{"crackBrightness":9.0,"crackDepth":6.0,"crackSpacing":15.0}`

## `texture.grain`

Grain (raster; menu: Effect › Texture).

Parameters: {intensity: 0..100 (40), contrast: 0..100 (50; the image's contrast, 50 leaves it as it is), grainType: "regular"|"soft"|"sprinkles"|"clumped"|"contrasty"|"enlarged"|"stippled"|"horizontal"|"vertical"|"speckle" ("regular")} adds grain in 1 pt grains (2 pt Enlarged, clumps Clumped, streaks Horizontal and Vertical); Sprinkles and Stippled use the background colour, white

Defaults: `{"contrast":50.0,"grainType":"regular","intensity":40.0}`

## `texture.mosaicTiles`

Mosaic Tiles (raster; menu: Effect › Texture).

Parameters: {tileSize: pt 2..100 (12), groutWidth: 1..15 (3; the grout is half a point wide per step), lightenGrout: 0..10 (9; how light the grout is)} lays the object in irregular tiles bevelled at their edges, with sunken grout between them

Defaults: `{"groutWidth":3.0,"lightenGrout":9.0,"tileSize":12.0}`

## `texture.patchwork`

Patchwork (raster; menu: Effect › Texture).

Parameters: {squareSize: pt 0..10 (4; 0 draws 1 pt squares), relief: 0..25 (8)} redraws the object in squares of the colour around their centres, raised to heights that follow its highlights and shadows, a little more or less at random, lit from the top left

Defaults: `{"relief":8.0,"squareSize":4.0}`

## `texture.stainedGlass`

Stained Glass (raster; menu: Effect › Texture).

Parameters: {cellSize: pt 2..50 (10), borderThickness: 1..20 (4; the lead between the panes, half a point wide per step, in the foreground colour: black), lightIntensity: 0..10 (3; a light behind the object's centre, fading out towards its corners)} redraws the object as single-coloured panes around random points about cellSize apart

Defaults: `{"borderThickness":4.0,"cellSize":10.0,"lightIntensity":3.0}`

## `texture.texturizer`

Texturizer (raster; menu: Effect › Texture).

Parameters: {texture: "brick"|"burlap"|"canvas"|"sandstone" ("canvas"; surfaces made in code), scaling: % 50..200 (100), relief: 0..50 (4), lightDirection: "bottom"|"bottomLeft"|"left"|"topLeft"|"top"|"topRight"|"right"|"bottomRight" ("top"), invert: bool (false; turns the surface's heights over)} paints the object on a surface in relief

Defaults: `{"invert":false,"lightDirection":"top","relief":4.0,"scaling":100.0,"texture":"canvas"}`

## `video.deinterlace`

De-Interlace (raster; menu: Effect › Video).

Parameters: {eliminate: "odd"|"even" ("odd"; which field lines are taken out), create: "duplication"|"interpolation" ("duplication"; a line taken out becomes a copy of the line above, or the average of the lines above and below)} the field lines are the rows of the document's raster grid (Document Raster Effects Settings › Resolution), numbered from 1 at the top of the page

Defaults: `{"create":"duplication","eliminate":"odd"}`

## `video.ntscColors`

NTSC Colors (raster; menu: Effect › Video).

Parameters: {} makes colours a television signal can't carry (luma plus chroma past 110 % of white, or luma minus chroma below −20 %) less saturated, keeping their brightness

Defaults: `{}`

## `adjust.brightnessContrast`

Brightness/Contrast (geometry; menu: Effect › Color Adjustments).

Parameters: {brightness: -100..100 (0; bends the tones, black and white stay), contrast: -100..100 (0)} recolours the object's fills, strokes, type, meshes and embedded images (each colour keeps its model)

Defaults: `{"brightness":0.0,"contrast":0.0}`

## `adjust.curves`

Curves (geometry; menu: Effect › Color Adjustments).

Parameters: {points: "x,y x,y …" or [[x, y], …] (input, output 0..255; a smooth monotone curve through them, flat past the ends; "0,0 128,128 255,255"), channel: "rgb"|"red"|"green"|"blue" ("rgb")} recolours as Brightness/Contrast does

Defaults: `{"channel":"rgb","points":"0,0 128,128 255,255"}`

## `adjust.hueSaturation`

Hue/Saturation (geometry; menu: Effect › Color Adjustments).

Parameters: {hue: deg -180..180 (0), saturation: -100..100 (0), lightness: -100..100 (0), colorize: bool (false; true: every colour takes hue `hue` (0..360) at saturation (100 + saturation) / 2 %)} recolours as Brightness/Contrast does

Defaults: `{"colorize":false,"hue":0.0,"lightness":0.0,"saturation":0.0}`

## `adjust.levels`

Levels (geometry; menu: Effect › Color Adjustments).

Parameters: {inputBlack: 0..255 (0), inputWhite: 0..255 (255), gamma: 0.1..10 (1; above 1 lightens the midtones), outputBlack: 0..255 (0), outputWhite: 0..255 (255), channel: "rgb"|"red"|"green"|"blue" ("rgb")} recolours as Brightness/Contrast does

Defaults: `{"channel":"rgb","gamma":1.0,"inputBlack":0.0,"inputWhite":255.0,"outputBlack":0.0,"outputWhite":255.0}`

## `adjust.shiftToColor`

Shift to Color (geometry; menu: Effect › Color Adjustments).

Parameters: {color: "#rrggbb" ("#ff8000"), amount: 0..100 % (50), preserveLightness: bool (true: colours take the target's hue and saturation and keep their lightness; false: they mix with it)} recolours as Brightness/Contrast does

Defaults: `{"amount":50.0,"color":"#ff8000","preserveLightness":true}`

## `adjust.temperatureTint`

Temperature/Tint (geometry; menu: Effect › Color Adjustments).

Parameters: {temperature: -100 (cooler) .. 100 (warmer) (0), tint: -100 (greener) .. 100 (more magenta) (0)} recolours as Brightness/Contrast does

Defaults: `{"temperature":0.0,"tint":0.0}`

## `warp.arc`

Arc (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.arcLower`

Arc Lower (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.arcUpper`

Arc Upper (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.arch`

Arch (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.bulge`

Bulge (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.shellLower`

Shell Lower (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.shellUpper`

Shell Upper (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.flag`

Flag (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.wave`

Wave (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.fish`

Fish (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.rise`

Rise (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.fisheye`

Fisheye (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.inflate`

Inflate (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.squeeze`

Squeeze (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `warp.twist`

Twist (geometry; menu: Effect › Warp).

Parameters: {bend: % (-100..100, 50), horizontal: % distortion (0), vertical: % distortion (0), orientation: "horizontal"|"vertical"}

Defaults: `{"bend":50.0,"horizontal":0.0,"orientation":"horizontal","vertical":0.0}`

## `pathfinder.add`

Add (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.intersect`

Intersect (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.exclude`

Exclude (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.subtract`

Subtract (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.minusBack`

Minus Back (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.divide`

Divide (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.trim`

Trim (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.merge`

Merge (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.crop`

Crop (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `pathfinder.outline`

Outline (geometry; menu: Effect › Pathfinder).

Parameters: {} (groups and layers: live Pathfinder over the members)

Defaults: `{}`

## `cropMarks`

Crop Marks (geometry; menu: Effect).

Parameters: {style?: "roman"|"japanese" (default: the japaneseCropMarks preference when applied)} trim marks in [Registration] around the object's bounds, following it

Defaults: `{}`

