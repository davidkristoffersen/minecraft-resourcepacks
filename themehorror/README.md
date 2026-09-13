# ThemeHorror

The Haunt plugin's companion layer, for Minecraft Java 26.2+, **no mods**.

Download: [`ThemeHorror-2.0.0.zip`](ThemeHorror-2.0.0.zip)

A layer that stays loaded and paints only *states* the server puts a player in, so
Haunt can switch the look per player without a pack reload anyone could notice:

- blood hearts that drip on the absorbing, blinking and frozen heart sprites - the
  cues Haunt plays on a victim during an event;
- the new moon repainted as a blood moon - the `bloodmoon` cue parks a player's sky
  on that phase while the director is armed. A natural new-moon night shows it to
  everyone with the pack, one night in eight.

Nothing everyday is touched, so it never fights another theme over a file. Derived
from the vanilla textures in the installed client jar when the pack is built.
`python3 build.py` builds; shared code lives in `../themelib.py`.
