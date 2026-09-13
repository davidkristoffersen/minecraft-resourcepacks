# minecraft-resourcepacks

Server resource packs for a Paper 26.2 server, all working on a vanilla client
with **no mods**. Each folder is one pack: its `build.py`, its tests and the
current zip, which the server hands to players as an optional server resource
pack.

| Pack | What | Download |
|---|---|---|
| [GlassFrame](glassframe/) | Glass with no borders at all, blocks and panes, so a window or floor reads as one clean sheet. Pairs with a plugin that draws the outline back only where the glass actually stops. | [`GlassFrame-2.8.3-borderless.zip`](glassframe/GlassFrame-2.8.3-borderless.zip) |
| [ServerUI](serverui/) | Pixel icons at the emoji code points the server's dialog menus use, drawn into the default font. Without the pack the menus show the same symbols in Unifont. | [`ServerUI-1.1.0.zip`](serverui/ServerUI-1.1.0.zip) |
| [ThemeCalm](themecalm/) | Theme layer for the main server: warm gold hotbar frame, warmer sun, a soft chime on every menu click. | [`ThemeCalm-1.0.0.zip`](themecalm/ThemeCalm-1.0.0.zip) |
| [ThemeLab](themelab/) | Theme layer for the test server: teal hearts, cyan experience bar and hotbar frame, a digital blip on every menu click. | [`ThemeLab-1.0.0.zip`](themelab/ThemeLab-1.0.0.zip) |
| [ThemeHorror](themehorror/) | Theme layer the Haunt plugin wears while armed: blood moon, dripping hearts, heavier rain, closing vignette, a chest lid for every click. | [`ThemeHorror-1.0.0.zip`](themehorror/ThemeHorror-1.0.0.zip) |

The three theme layers share `themelib.py`: a pack that ships only the files it
changes, every texture derived from the installed client jar at build time, the
click sound a remap of vanilla sound events.

Every zip name carries its version: a new build is a new file and a new sha1,
so no client is ever served different bytes under a name it has cached.

## Working on a pack

This repo is a git submodule of the server repo (`resourcepacks/` there), and the
server's `publish-packs.py` is the one command that ships a change: it rebuilds
every pack, commits and pushes here, waits for GitHub to serve the new zip, and
writes the url and sha1 into the server's look-packs configs.

- `python3 build.py [pack]` - build; each pack's zip lands in its folder.
- `python3 bump.py <pack> major|minor|patch "note"` - the only way a version
  changes. Patch = the same thing drawn or tuned better, minor = something new,
  major = the pack changes shape. Rewrites the READMEs, appends to `CHANGELOG.md`,
  rebuilds.
- Publishing a changed zip under an unchanged version is refused upstream: the
  publisher bumps the patch number itself when it finds that, so a forgotten bump
  costs a version number, never a stale client cache.
