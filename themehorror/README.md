# ThemeHorror

The layer the Haunt plugin wears while its director is armed, for Minecraft Java
26.2+, **no mods**.

Download: [`ThemeHorror-1.1.0.zip`](ThemeHorror-1.1.0.zip)

Blood moon in every phase, heavier rain, a vignette that closes in, every menu click
a chest lid falling shut - and dripping blood hearts painted on the *state* sprites
only (absorbing, blinking, frozen), so they appear during a Haunt moment, when the
server plays the `absorbing` cue on the victim, and never fight another theme over the
everyday hearts. Everything is derived
from the vanilla textures in the installed client jar when the pack is built, and the
click is a remap of vanilla sound events - no audio is shipped. Haunt pushes it with
`/lookpacks ThemeHorror on` when the director arms and pops it when it disarms.
`python3 build.py` builds; shared code lives in `../themelib.py`.
