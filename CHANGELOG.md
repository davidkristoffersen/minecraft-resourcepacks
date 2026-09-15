# Changelog

One entry per published version, newest first.

## MobDesigner 1.3.0

a costume draws as itself in the inventory: one icon per design per slot, selected on custom_model_data like the eggs

## Camera 1.7.0

six polaroid tints chosen from the photo's own average colour, replacing the map_color tint 26.3 removed

## ThemeLab 1.0.1

Patch bump by publish-packs.py: the pack changed without a version bump.

## ThemeHorror 2.3.3

Patch bump by publish-packs.py: the pack changed without a version bump.

## ThemeCalm 1.0.1

Patch bump by publish-packs.py: the pack changed without a version bump.

## ServerUI 1.13.3

Patch bump by publish-packs.py: the pack changed without a version bump.

## MobDesigner 1.2.1

Patch bump by publish-packs.py: the pack changed without a version bump.

## Camera 1.6.1

26.3 removed the map_color tint source, so the filled_map definition named something the client does not know and every photo and every real map fell back to the missing-model cube

## MobDesigner 1.2.0

Every voice synthesised: 57 mono OGG lines, one per design per ambient/hurt/death, and no vanilla sound events left in the pool

## ServerUI 1.13.2

Patch bump by publish-packs.py: the pack changed without a version bump.

## Camera 1.6.0

the three cameras wear three shells (cream, warm, cold) so they are told apart in the hand as well as the inventory, and the compass definition gains the zoom camera for when it is empty

## Camera 1.5.0

the held camera is solid: its faces take a gap-filled copy of the drawing, plain body sides and a viewfinder eyepiece on the back, so the raised camera is no longer see-through

## Camera 1.4.0

aiming raises the camera in first person too: a using_item model with a raised pose, since the client only lifts the arm in third person

## ServerUI 1.13.1

Patch bump by publish-packs.py: the pack changed without a version bump.

## MobDesigner 1.1.0

Beyond the costume: wings for the Vampire and Arsonist, a staff, a cudgel and a knife as hand items, a bomb and a die as creeper hats, aura sprites for eight designs, a voice per design (pools of vanilla sounds plus three synthesised signatures) and the Hexer - the Illusioner repainted whole

## MobDesigner 1.0.0

First release: a costume (armour-layer texture) for 18 designed humanoids and a spawn egg picture for all 24 designs of the Mob Designer

## ServerUI 1.13.0

🥚 as an icon, and the MobDesigner panels: the designs' eggs beside the plain ones, four costumes beside the bare zombie and skeleton

## ServerUI 1.12.0

📦 as an icon, for the shelf that gathers every plugin's custom items

## ServerUI 1.11.0

◀ as an icon, for a paged item shelf

## Camera 1.3.0

a real three-dimensional camera in the hand: the flat sprite in the inventory, a body, lens barrel and flash unit when it is held or raised to the face

## ServerUI 1.10.1

Camera panel: three cameras over film and a polaroid, two rows a side

## Camera 1.2.0

Flash camera and zoom camera: two more cameras drawn from the same body, and the spyglass item definition the zoom one wears

## ServerUI 1.10.0

Six more icons: 📡 server list, 🎭 texture cues, 📊 stats, 🎮 game mode, 🎞 video, 🔍 look up

## ServerUI 1.9.2

Banner glyphs hang into the dialog's own spacing (ascent 10/9): one body line, no blank lines

## ServerUI 1.9.1

Camera panel shows the film card too: three items a side at 2x

## Camera 1.1.0

Film: the blank polaroid the plugin's cheap film wears (items/map.json override, vanilla empty map as the fallback)

## ServerUI 1.9.0

Hub header banners: fading wings (U+E220/E221) and the icons at 3x in serverui:gui, positive spaces U+F809..F810, preview panel E118

## ServerUI 1.8.0

chest-grid frames in their own font serverui:gui (a panel and an accent per row count, negative spaces)

## ThemeHorror 2.3.2

veins shipped through themelib.font_picture, the generic font-picture helper

## ServerUI 1.7.1

veins panel redrawn from the split bitmap

## ThemeHorror 2.3.1

veins glyph split into two 256x256 cells - the client drops a glyph bigger than its 256x256 font texture

## ServerUI 1.7.0

veins panel for ThemeHorror; frozen-heart and frost panels retired

## ThemeHorror 2.3.0

veins as a title glyph in the pack's own font; frozen hearts and frost border back to vanilla

## ServerUI 1.6.0

Preview panel for the Camera pack (U+E120): the camera and a photo, without | with.

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
