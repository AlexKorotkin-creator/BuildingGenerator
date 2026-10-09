BuildGen - procedural building generator for Houdini + Unreal Engine
====================================================================

You draw the outline of a building in Unreal, hand the generator a few wall
blocks, and it builds the whole thing: walls along the contour, floor and
ceiling slabs, columns, stairs, a lift shaft, lights, storeys stacked on top of
each other, a roof with a parapet and a stair housing. Then you bake it into a
single Blueprint and walk through it.

The generator itself lives in Unreal as a Houdini Digital Asset. Houdini is the
calculator on the other end of a live session - you never build anything by
hand in it.

Free and open source (MIT licence). Use it for anything, personal or
commercial, change it, share it. What you build with it is yours to ship and
sell. Epic's building blocks are not included and stay under Epic's licence.
Full terms in LICENSE.txt, in this folder.
Source: https://github.com/AlexKorotkin-creator/BuildingGenerator

Built and tested with Houdini 21.0 and Unreal Engine 5.8.


WHERE EVERYTHING IS
-------------------
    Generator.hiplc           the Houdini scene - this is the file you open
    BuildGen_Setup_RU.html    the full step-by-step walkthrough (Russian).
                              Open it in any browser. It is a checklist: every
                              step has a tick box, and it remembers your ticks.
    BuildGen_Parameters.html  what every parameter of the generator does, tab
                              by tab, in the order they appear in the panel
    LICENSE.txt               the terms
    hda\                      BuildGen.hda - the generator itself
                              Rebuild_Blocks_From_UE*.hdalc - three tools that
                              turn Unreal meshes into blocks (see BLOCKS)
    geo\                      ten placeholder blocks, so the generator runs out
                              of the box without any content pack
    Scripts\                  helper scripts, see SCRIPTS at the bottom
    My_Buildings\             ready-made Unreal assets: the contour planner
                              widget, the contour spline, and the Python file
                              that does its arithmetic

Nothing here has to be installed into Houdini by hand. Houdini scans the "hda"
folder next to the scene file, so opening Generator.hiplc is enough - the
generator and the block tools appear as node types by themselves.


WHAT YOU NEED
-------------
- Houdini (Indie or commercial). Houdini Apprentice will NOT work: the free
  Apprentice licence does not include Houdini Engine, so no HDA can be loaded
  into Unreal at all. This is a SideFX licensing rule, not a limitation of this
  tool.
- Houdini Engine for Unreal (the plugin). Houdini Indie users get Houdini
  Engine Indie for free from SideFX.
- Unreal Engine 5.8.
- Blocks. Ten placeholder cubes are included, so you can press every button and
  see how it works right away. For a real building you bring your own blocks -
  your own meshes, or the free "City Sample Buildings" pack from Fab. Blocks
  are not included here; see BLOCKS below.
- Memory. Read the next section before you start - on heavy blocks this is the
  one thing that decides whether the run finishes at all.


MEMORY - SET THIS UP FIRST
--------------------------
The generator is not limited by your graphics card or your processor. It is
limited by memory, and it has to be set up once, before you open anything.

Houdini calculates the building while Unreal builds meshes out of what it has
already calculated. Both hold the geometry at the same time - the appetites do
not take turns, they add up.

    Light blocks (a few thousand primitives each): 32-64 GB of RAM and the
    default Windows paging file are fine. Skip the rest of this section.

    Heavy blocks (a wall of 700k primitives, an entrance of 3.3M): RAM plus
    paging file together must be at least 256 GB. This is a measured ceiling,
    not a recommendation: on such a kit Windows counted 129.9 GB for Houdini
    and 109.6 GB for Unreal at the same moment - 240 GB - and killed Houdini
    with "Out of Virtual Memory", taking a full day of work with it.

Paging file: Win+R -> sysdm.cpl -> Advanced -> Performance Settings -> Advanced
-> Virtual memory -> Change. Untick the automatic size, pick your SSD, choose
Custom size, and put THE SAME number in Initial size and Maximum size (with
128 GB of RAM: 160000 MB). Press Set, then OK three times, then reboot - a file
that size is only created when Windows starts. Different numbers are not
enough: Windows grows the file lazily and a sudden appetite outruns it.

Houdini's cache of intermediate results: Edit -> Preferences -> Objects and
Geometry -> SOP Cache tab. Set Memory Limit to 16384 MB and, under Manual
Overrides, set Memory to Always. Out of the box the limit is drawn but ignored
("Never"), and on heavy blocks the cache grows into tens of gigabytes. Cull
Level turning into -1 afterwards is normal: it means "manual, not from a
preset". These are Houdini's own preferences, not part of the scene file.

There is no HOUDINI_MEMORY_LIMIT variable - do not put one in houdini.env, it
looks like a safeguard and does nothing.


INSTALL
-------
In Houdini:

1. Unpack this folder anywhere you like.
2. Copy Scripts\123.py and Scripts\456.py into your Houdini user folder:
   Documents\houdini21.0\scripts\ . This is required, not optional - they keep
   the Houdini viewport from recalculating the building behind your back, which
   otherwise doubles every cook. Check it took: in the Python Shell,
   len(hou.node("/obj").eventCallbacks()) must return 1.
3. Open Generator.hiplc.

In Unreal:

4. Create a project - any template. It is convenient to keep it next to this
   folder.
5. Enable the Houdini Engine plugin and restart the editor.
6. Add these two lines to the end of <Project>\Config\DefaultEngine.ini:

       [DerivedDataCacheStores]
       InstalledLocal=(Base=Local, Path="%ENGINEVERSIONAGNOSTICUSERDIR%DerivedDataCache", Clean=true, DeleteUnused=false)

   Without them the editor spends about a quarter of an hour every hour tidying
   its cache on disk, in the middle of your working day. These two lines move
   that tidying to startup and switch the hourly visits off.
7. Copy the whole My_Buildings folder into <Project>\Content\ . Copy it whole:
   the planner widget is not one asset, all of its arithmetic lives in
   contour_widget.py next to it. Check it runs: right-click EUW_ContourReport
   -> Run Editor Utility Widget.
8. Import hda\BuildGen.hda into the Content Browser, plus the block HDAs you
   are going to build with.

Settings of the plugin, once per project (Edit -> Project Settings -> Plugins
-> Houdini Engine): Session Type = Shared Memory Buffer, Server Name = hapi,
Shared Memory Buffer Size = 4096, Buffer Cyclic on, and - important - turn
"Sync With Houdini Cook" OFF, it makes the editor order a new cook forever.


THE ORDER THAT MATTERS
----------------------
Half of all failures come from doing the right things in the wrong order.

1. HOUDINI OPENS THE SESSION, UNREAL JOINS IT. In Houdini: the Houdini Engine
   SessionSync panel -> Shared Memory, name hapi, 4096 MB, Ring Buffer ->
   Start. Only then, in Unreal: Houdini Engine -> Connect to Session.
   Never press "Create Session" in Unreal. It starts a separate headless
   process, your blocks end up inside it instead of your Houdini, and nothing
   works after that.
2. BLOCKS INTO THE VIEWPORT BEFORE THE GENERATOR. Drag every block HDA into
   the level and let each one draw itself. Each becomes a node in the live
   Houdini session, and the generator then reads it straight from there. Put
   the generator in first and the blocks have to travel through the bridge as
   raw geometry - that is minutes per block, every cook.
3. THE GENERATOR, AND ITS CURVE INPUT FIRST. Drag BuildGen into the level and
   immediately assign the contour curve to its Curve Input - before sides,
   before blocks, before anything else.
4. SIDES AND NUMBERS NEXT. Number of sides first of all, then blocks per side,
   offsets, copies, bend angles.
   Never touch an input slot before the sides exist. The slots are drawn by a
   multiparm after the sides are set, and assigning a block to a slot that does
   not exist yet takes Houdini down with it, session and all.
5. BLOCKS INTO SLOTS UNDER PAUSE. Press Ctrl+Alt+P ("Pause Houdini Engine
   Cooking"), assign every block slot and every Corner Source, and only then
   lift the pause. Each assignment is an input change, and each input change
   orders a cook - twenty-five slots without a pause is twenty-five cooks.
   Do not save the level while the pause is on.
6. RELEASE THE PAUSE AND WAIT. In the log you first get silence and a line
   "Stopped processing after N seconds", and only afterwards "Cooking Started".
   That is not a freeze: the silence IS the calculation. Both editors showing
   "Not responding" is normal - check the CPU load of the processes instead of
   clicking on them.

The full route, with every tick box, is in BuildGen_Setup_RU.html.


THE RULE OF SPEED
-----------------
Keep the Houdini network window parked at /obj, and pin it (the pin icon in the
top right corner of the network editor).

While the window is inside the generator, Houdini must keep a fresh picture on
the screen, so every click you make in Unreal means "draw the whole building
again". The same floor: window inside - 8 recalculations; window at /obj - one.

For the same reason the display flag inside the generator container sits on an
empty null called UE_VIEWPORT_STUB, and the scripts from step 2 keep it there.
If a ceiling slab suddenly shows up in the Houdini viewport, the flag has
slipped - click the null and it is back. Check that after the first block of
every new storey.


FREEZING - WHY A BIG BUILDING STAYS FAST
----------------------------------------
Everything is built by one chain, so a new storey would normally recalculate
everything below it. The generator has six freeze stages, each a pair of
FREEZE / UNFREEZE buttons on its own tab: blocks, floor and ceiling, columns,
stairs, the storey itself, and the stack of finished storeys. A frozen stage is
a hard lock on a seam node: what was calculated stays, and later stages do not
touch it.

Three rules that save the most time:

- Freeze a stage LAST, after everything that feeds it is set. A value set after
  the freeze silently does not apply. The classic one: Collision -> Wall
  Thickness must be set BEFORE freezing the blocks, or the walls keep their old
  collision and you only find out in play mode.
- Columns cannot be frozen before the stairs exist - the column grid is cut by
  the lift shaft, and lights grow out of that same grid, so the order is:
  stairs and shaft -> columns -> lights.
- Freeze Floor before adding the next storey, not after.

Press several buttons as one batch under the cooking pause whenever you can:
on heavy blocks Unreal spends about 150 seconds rebuilding meshes after EVERY
cook, no matter how small the change, so what counts is the number of cooks,
not the calculation time.

A freeze only lives inside the running Houdini session. Restart Houdini and you
freeze again.


BLOCKS
------
A block is just a mesh: one wall panel, a corner, an entrance. The generator
repeats and bends them along the contour.

Included: ten placeholder cubes in the "geo" folder, named like the blocks of
the Epic kit. They are there so the generator runs on a fresh machine without
any content pack. Replace them with anything you like.

Name the block actors in the Unreal outliner for the ground floor like this -
the contour planner looks them up by these labels:

    CL_0    corner block, a side starts with it
    EN      entrance
    W_1, W_2, ...   ordinary wall blocks
    W_2+N   the one that gets multiplied to fill the side to its length;
            the planner works out how many copies

Making blocks out of your own Unreal meshes - the "Rebuild Blocks From UE"
tools in the hda folder. They repack what Unreal sent into a .bgeo.sc cache
plus a light HDA that reads it, and that HDA is what you drop into the level:

    V1   splits vertices along the UV seams, then cleans up edges. Needs the
         paid Modeler plugin.
    V2   cleans up edges without the seam protection. Needs Modeler.
    V3   no cleanup, standard Houdini normals. Needs nothing extra - start
         here if you do not own Modeler.

Recomputing normals is not optional: meshes lose their normals on the way back
from Unreal.

If you take the blocks from the free "City Sample Buildings" pack on Fab: in
the Content Browser (not the viewport - that command is greyed out in UE 5.8)
select the meshes, right-click -> Nanite -> Disable FIRST, then right-click ->
Send to Houdini. Houdini only reads the fallback mesh of a Nanite asset, a
reduced faceted version, and your blocks would arrive broken. Nanite is turned
back on later, in Unreal, on the baked meshes.

Epic's blocks are Epic's content: you download them yourself, and they are not
redistributable.


THE "BLOCKS FOLDER" PARAMETER (on the "Unreal" tab)
---------------------------------------------------
In Houdini you never touch it. Default: $HIP/geo - the "geo" folder next to the
scene file.

In Unreal it is the one thing you may have to set: $HIP there points at a
temporary session folder. Open the "Unreal" tab and type the absolute path of
your geo folder once, e.g.

    D:/BuildGen/geo


THE CONTOUR
-----------
The shape of the building in plan is an Unreal spline: BP_ContourSpline from
the My_Buildings folder. Drop it into the level, set its Location to zero,
Closed Loop on, and put one point per side.

The planner widget (EUW_ContourReport) reads the spline and your recipe of
blocks per side, and answers with the numbers the generator wants: how many
copies of the repeating block each side takes, and the bend angle at each
corner. CALCULATE PLAN, check the report, then APPLY TO SPLINE moves the spline
points onto whole blocks.

Two things before you press CALCULATE PLAN:

- Houdini Engine -> "Refine All Houdini Proxy Meshes To Static Meshes". A block
  that is still a proxy mesh has no mesh to measure, so the widget falls back
  to actor bounds and a four-metre block reports forty-five. The giveaway is in
  the report itself: BLOCK WIDTHS with the source "bounds" instead of "mesh",
  widths in thousands of centimetres, Copies = 1 everywhere.
- Read the DRAWN column top to bottom and compare it with the outline on the
  screen: the long side has to be the long one. Side N is counted from spline
  point N, and point 0 is not necessarily the one that looks first to you.

Type the numbers into the generator carefully. Two of the worst runs we had
were plain typing mistakes: one extra copy on a side made the floor contour
cross itself, and a wrong bend angle left a storey short of its corner.


THE SLAB CURVE (the floor between storeys)
------------------------------------------
The slab is one thing doing two jobs: the ceiling of a storey and the floor of
the storey above. It is filled from a closed contour curve, and that curve
lives inside the asset itself. Every building has its own outline, so the
generator ships WITHOUT one - you draw it once:

1. Select BP_ContourSpline in the outliner, make sure its Location is zero,
   rotate it 90 degrees, then Houdini Engine -> Houdini Node Sync -> Send. The
   contour arrives in Houdini.
2. In Houdini, trace that shape with a separate "curve" node: one closed
   stroke, and disconnect its input. It has to be a single closed primitive -
   snapping the last point onto the first is NOT closing it, and the slab comes
   out empty without any error.
3. Copy that node (Ctrl+C). Inside the BuildGen node there is a black network
   box labelled "Curve" - paste it there and wire it into "ceiling_offset",
   input 0, replacing what was there.
4. Press the button "Apply Slab Curve To Type", on the "Floors / Blocks" tab
   right under "Make Ceiling". It stores the curve in the asset. The button
   works from Unreal as well.
5. In Unreal, press Rebuild - while the generator is still empty, before you
   start assigning blocks. Then switch "Make Ceiling" on.

The read-only line "Slab Curve Status" underneath reports the last press: how
many points were stored and the new size of the asset file.

Do NOT use Houdini's "Save Node Type" for this. That command writes the entire
contents of the node you are standing on back into the asset, and a working
node is not an exact copy of the asset - whatever it happens to be missing at
that moment is dropped, and you lose parts of the generator with it.
"Apply Slab Curve To Type" exists to avoid exactly that: it copies the curve
into a fresh instance, compares the node list before and after, and puts the
backup back if anything would go missing. Every press also leaves a timestamped
.hda backup next to the asset, so steps 4-5 are safe to repeat as often as you
like.


COLLISION
---------
Collision -> Wall Thickness is how deep a block is, in metres, and it is one
number for the whole building. Measure it on the DEEPEST block of your kit,
usually the entrance, not on an ordinary wall: take the block's mesh in the
Content Browser, read "Approx Size" in the static mesh editor, take the
smallest horizontal number - the depth, not the length - and divide by 100.
An ordinary wall is 201 cm deep while the entrance is 544: measure the wall and
the entrance recess ends up with no collision and the player falls through it.

Set it BEFORE you freeze the blocks.


WINDOWS: TRANSPARENT GLASS vs NANITE
------------------------------------
- Background building, nobody walks inside: use the pack's default Fake
  Interior window material. Nanite can be enabled everywhere.
- Playable building with a real interior: keep transparent glass, and do NOT
  enable Nanite on those meshes - a Nanite mesh with a transparent material
  falls back to the engine's default (brown) material.


BAKING TO UNREAL
----------------
Bake to Blueprint, with "Pack" set to "Make Instant Static Mesh". You get one
Blueprint actor, and repeated blocks become instanced static mesh components.

Enable Nanite after the bake, not before. Doors are added afterwards, in the
Blueprint - re-baking wipes anything you added there, so bake first and build
on top.


SCRIPTS
-------
    123.py, 456.py    the display guard, described in INSTALL step 2. Copy both
                      into Documents\houdini21.0\scripts\ . The bodies are
                      identical; one runs when Houdini starts, the other when a
                      scene is loaded.
    save_from_ue.py   writes meshes that arrived from Unreal into the geo
                      folder as .bgeo.sc. Same thing as the "Save Blocks From
                      UE" button on the generator.
    import_bgeo.py    the way back: loads every .bgeo.sc from the geo folder
                      into a subnet in Houdini.
    For_Shelfs.txt    ready-made one-liners for shelf buttons for those two.
    contour_report.py the contour planner as a plain script, for Unreal's
                      Cmd console; the widget is the friendly version of it.
    make_euw.py       recreates the planner widget asset, if it ever breaks.
    freeze_*.py, add_freeze_floor_button.py, type_*.py, ceiling_visibility.py
                      the scripts that installed the freeze stages and other
                      features into the asset. You do not need them to use the
                      generator - they are here so the tool stays repairable.
    cook_watch.py, cpu_watch.ps1
                      diagnostics: what recalculated and when, and how much
                      processor and memory the two editors are using.

All of them work out of the folder they are in - nothing has a fixed path.


IF SOMETHING GOES WRONG
-----------------------
BuildGen_Setup_RU.html ends with a diagnosis table: the line you see in the
Unreal log on the left, what it actually means on the right. The short version:

- A cook "finishes" in a fraction of a second and nothing appears, or the log
  says "Invalid id" / "No valid Houdini Engine session": the actor is holding
  node ids of a session that is gone. Delete the BuildGen actor and place it
  again. Rebuild will not fix it and makes things worse.
- Lots of nodes ending in _Merge in Houdini: the blocks were not in the live
  session when you assigned them, so they travelled through the bridge as raw
  geometry. Only one such node is normal - the contour curve.
- Cooks going round and round and never stopping: "Sync With Houdini Cook" is
  on, or the display flag is on the asset instead of the stub null.
- Houdini closed by itself: almost always an input slot touched before the
  sides were set.


LICENCE / CREDITS
-----------------
This generator (the BuildGen asset, the scene and the scripts) is free and open
source under the MIT licence. Full terms in LICENSE.txt.

The building blocks are NOT part of this package. Epic's kits belong to Epic
Games and are covered by the licence of the pack you downloaded from Fab. You
get them yourself; do not redistribute them.

Made with Houdini Indie.
