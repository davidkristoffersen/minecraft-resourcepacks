# Camera

The look of the Camera plugin's camera and its photos, for Minecraft Java 26.2+, **no mods**.

Download: [`Camera-1.3.0.zip`](Camera-1.3.0.zip)

The plugin's camera is a recovery compass and its photos are filled maps - vanilla items,
so a player without this pack still sees something sensible. The pack repaints the three
vanilla item definitions only where the plugin has set `custom_model_data`, and puts the
vanilla definition back as the fallback:

- the camera, empty (dark film slot, red light), loaded (a paper tab peeks out, green light)
  and flashing for a few ticks after a shot;
- a photo as a polaroid: a white card whose picture is tinted by the item's `map_color`,
  which the plugin sets to the photo's own average colour;
- film as the same card before a picture is on it (a dark window with a sheen and the
  camera's stripe) - the plugin's cheap film is an empty map underneath, so a player without
  the pack sees an empty map named Film.

Held in hand a photo is still the big map picture - the client decides that by item type -
so the polaroid is what you see in the inventory, in the hotbar and on the ground.

`python3 build.py` builds; the art is the tables at the top of `build.py` and
`preview.png` shows every sprite at 8x. Shared code lives in `../themelib.py`.
