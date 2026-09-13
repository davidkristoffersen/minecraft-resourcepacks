# Changelog

One entry per published version, newest first.

## ServerUI 1.5.0

frost-border panel for ThemeHorror replaces the nausea one

## ThemeHorror 2.2.0

blood veins on the frozen cue's screen border; the nausea paint dropped (additive, tinted by the client)

## ServerUI 1.4.2

nausea preview panel wrote past the row end - a corrupt PNG the client rejected, failing every pack

## ServerUI 1.4.1

nausea panel shows the haze as rendered, not the raw mask

## ThemeHorror 2.1.1

nausea overlay drawn for the client's additive tint: full red, wider reach

## ServerUI 1.4.0

preview panels for ThemeHorror's hunger and nausea cues

## ThemeHorror 2.1.0

raw drumsticks for the hunger cue, a veined overlay for the nausea cue

## ServerUI 1.3.0

Several preview panels per pack: ThemeHorror shows the blood moon and each cue heart (absorbing, frozen, blink) on its own panel.

## ServerUI 1.2.3

Horror preview shows the repainted new moon.

## ThemeHorror 2.0.0

A companion layer that stays loaded: only state sprites (absorbing/blinking/frozen hearts) and the new moon as a blood moon for the bloodmoon cue. Rain, vignette, the other moons and the click sound are gone - nothing everyday is touched, so Haunt switches the look per player with no pack reload.

## ServerUI 1.2.2

Horror preview follows the darker blood hearts.

## ThemeHorror 1.1.1

Darker blood on the state hearts - the first shade read as plain red beside a vanilla heart.

## ServerUI 1.2.1

ThemeHorror's preview shows the absorbing (event) hearts on the 'with' side.

## ThemeHorror 1.1.0

Blood hearts move to the state sprites (absorbing, blinking, frozen), so they show during a Haunt moment - the absorbing cue ServerMenus plays on the victim - and never fight another theme over the everyday hearts.

## ServerUI 1.2.0

Pack previews: one 'without | with' picture per look pack (GlassFrame, ServerUI, ThemeCalm, ThemeLab, ThemeHorror) as glyphs at U+E100-U+E104, drawn from the vanilla textures and the packs' own build code; shown on the Look Packs pack page for clients with this pack loaded.

## ThemeHorror 1.0.0

First release: blood moon in every phase, darker dripping hearts, heavier rain, a closing vignette, a chest lid for every menu click. Worn by the Haunt plugin while its director is armed.

## ThemeLab 1.0.0

First release: teal hearts, cyan experience bar and hotbar frame, a digital blip for every menu click. The test server's layer.

## ThemeCalm 1.0.0

First release: warm gold hotbar frame, a warmer sun, a soft amethyst chime for every menu click. The main server's layer.

## GlassFrame 2.8.3

Back to the 2.5.0 glass: specks where vanilla puts them, stained glass untouched

## ServerUI 1.1.0

Progress bars: 21 glyphs at U+E000-U+E014 (a 22x8 frame filling in 5 % steps), emitted by ServerMenus only for clients that report the pack loaded - TPS, Haunt weights, player health, the tier ladder.

## GlassFrame 2.8.2

Stained glass back to vanilla alpha - thinning the bars only uncovered the hole their opacity was hiding

## GlassFrame 2.8.1

Specks pulled two texels in from the edges, clear of where a 2px outline bar runs

## GlassFrame 2.8.0

Stained glass thinned to 65% again - the GlassRim bars are made of it and are see-through once more

## ServerUI 1.0.1

Pack icon: a menu button carrying a yellow ⚡ and a label, the thing the pack changes.

## GlassFrame 2.7.2

Pack icon: four glass blocks as one sheet with a single outer frame - what the pack plus GlassRim gives you.

## GlassFrame 2.7.1

Deterministic zip: fixed entry timestamps, so a rebuild of unchanged models gives the same sha1. Models unchanged. Shipped zip now sits at the pack root; evidence builds stay in dist/.

## ServerUI 1.0.0

First release: 81 8x8 icons at the emoji and symbol code points the server's menus use, in the default font.

## GlassFrame 2.7.0

Stained glass back to vanilla - the GlassRim bars are opaque now, so nothing had to be thinned for them.
