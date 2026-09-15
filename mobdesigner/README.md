# MobDesigner

The look of the Mob Designer's designed mobs (the CustomDifficulty plugin), for Minecraft Java 26.2+, **no mods**.

Download: [`MobDesigner-1.2.1.zip`](MobDesigner-1.2.1.zip)

A vanilla client draws every zombie from one texture, and nothing the server sends can pick
another per mob. What it does draw per mob is the **armour layer**: an item in an armour slot
carrying an `equippable` component with an `asset_id` is rendered over the mob as
`assets/mobdesigner/equipment/<design>.json` says. So a design's "skin" is a costume: the
plugin puts a carrier item (leather armour with no armour points, unbreakable, never dropped)
into every armour slot the design left empty, and this pack draws hood, coat, boots and face
over the mob's own skin. Only humanoids have that layer - zombies, husks, drowned, skeletons
and their kin. A creeper cannot wear anything, so its designs get an egg and nothing more.
Without the pack the asset id is unknown and the client draws nothing for it: the plain mob.

Every design also has a **spawn egg**: the vanilla egg of its base mob with `custom_model_data`
strings[0] = the design's id. The pack repaints the five egg item definitions (zombie, husk,
drowned, skeleton, creeper) only for those strings and falls back to the running client's own
definition, so real eggs are untouched. 26.2's eggs are little portraits of the mob; a design's
egg is that portrait recoloured, wearing the costume's loudest piece, with the design's emblem
as a badge in the corner.

`build.py` holds every design as a list of costume features (a hood, a cape, glowing eyes, a
chest emblem, scales, embers …) painted onto the 64x32 armour layout, and the egg's colours
and badge. `preview.png` shows every egg at 4x beside a front view of the dressed mob - look at
it after every change. Keep `VARIANTS` in step with `Skins.SKINS` in the plugin.

Textures are derived from the installed client jar at build time; nothing of Mojang's is vendored.
