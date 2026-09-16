# ThemeHorror

The Haunt plugin's companion layer, for Minecraft Java 26.2+, **no mods**.

Download: [`ThemeHorror-2.3.5.zip`](ThemeHorror-2.3.5.zip)

A layer that stays loaded and paints only *states* the server puts a player in, so
Haunt can switch the look per player without a pack reload anyone could notice:

- blood hearts that drip on the absorbing and blinking heart sprites - the cues Haunt
  plays on a victim during an event (not the frozen ones: a real freeze is vanilla's);
- the Hunger effect's rotten drumsticks as raw, bleeding meat (the `hunger` cue);
- blood veins over the whole screen, as one glyph of the pack's own font
  (`themehorror:veins`) that ServerMenus' `veins` cue sends as a title - so the server
  draws them exactly when it means to, and no vanilla state ever wears them;
- the new moon repainted as a blood moon - the `bloodmoon` cue parks a player's sky
  on that phase while the director is armed. A natural new-moon night shows it to
  everyone with the pack, one night in eight.

Nothing everyday is touched, so it never fights another theme over a file. Derived
from the vanilla textures in the installed client jar when the pack is built.
`python3 build.py` builds; shared code lives in `../themelib.py`.
