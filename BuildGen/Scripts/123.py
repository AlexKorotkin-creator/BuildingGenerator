# 123.py - Houdini runs this once at startup (456.py runs on every scene load).
#
# WHY THIS EXISTS
# Houdini Engine (Session Sync) creates its bridge nodes in /obj with the
# DISPLAY FLAG ON. With the viewport in Auto Update, Houdini must re-cook
# whatever is displayed. For a heavy HDA that means the generator is computed
# TWICE for everything Unreal does:
#     Unreal asks for a cook  -> HAPI cooks the asset       142 s
#     Unreal builds outputs   -> meshes, Nanite, tangents    40 s
#     the viewport notices    -> Houdini cooks THE SAME node 142 s
#     Unreal polls the cook count, sees it changed -> asks for a cook again ...
# and the same happens on every input Unreal connects during a Rebuild.
#
# HOW WE BREAK IT (04-09-2026): THE VIEWPORT STUB
# Unreal does NOT care which node inside the container holds the display flag.
# From the plugin source:
#   HoudiniOutputTranslator.cpp - "const bool bIsSopAsset = AssetInfo.nodeId
#     != AssetInfo.objectNodeId" -> our HDA is a SOP asset, so outputs are
#     gathered from the HDA NODE ITSELF (GatherOutputsNodeId = AssetInfo.nodeId),
#     never from the container's display SOP.
#   HoudiniOutputTranslator.cpp:2128 - "currentHGPO.bIsVisible =
#     CurrentHapiObjectInfo.isVisible" -> the only flag Unreal reads is the
#     display flag of the OBJ CONTAINER. Hidden container = no components.
#   HoudiniEngineScheduler.cpp:425 - Unreal cooks the asset node (and its
#     output nodes) by node id, explicitly. It never asks for "the display SOP".
# So: keep the CONTAINER visible (Unreal needs that), and give the container a
# cheap empty null as its display SOP. Houdini's viewport then cooks the null;
# the generator is only ever cooked when Unreal asks for it. Once, not twice.
#
# WHAT THIS COSTS YOU
# The building is no longer drawn in the Houdini viewport. Press the shelf
# button (BuildGen show/hide) to look at it - that puts the generator back on
# display and the next viewport update WILL cook the whole floor.
#
# MEASURED ON THE BUILDGEN FLOOR (03-09-2026, same floor every time):
#   everything hidden ................ input upload    0.7 s   cook 247 s
#   asset node visible ............... input upload 2426.7 s   cook 249 s
# The stub is meant to give the first line's speed with the second line's
# output: nothing heavy is ever on display, yet the container stays visible.

import hou

# The OBJ node Houdini Engine creates for YOUR asset. Change this one line.
ASSET_PREFIX = "buildgen"

# Name of the cheap null we park the display flag on.
STUB_NAME = "UE_VIEWPORT_STUB"

# True  = viewport stub (container stays visible, Unreal keeps working).
# False = fall back to the old two-pass workflow driven by HIDE_ASSET_NODE.
USE_VIEWPORT_STUB = True

# Everything else Houdini Engine puts in /obj: inputs, curves, merges.
#
# 04-09-2026: "SM_BLDG" REMOVED from this list on purpose. The block HDAs are
# not throwaway inputs - they are actors the user keeps in the level and reuses
# for the next building. Hidden here, Unreal gathers no outputs from them
# (HoudiniOutputTranslator.cpp: "if (!bIsVisible && !bIsInstanced) continue;"),
# so every generator Rebuild wiped their meshes and left empty actors behind.
# Hiding blocks was measured at 46 s out of 2473 - the saving lives in the
# stub, not here. Do not put "SM_BLDG" back.
HIDE_PREFIXES = ("HoudiniSplineComponent",)
HIDE_SUFFIXES = ("_Merge",)

# Legacy switch, only used when USE_VIEWPORT_STUB is False:
# hide the asset node itself -> fast upload, but NO output until show_asset().
HIDE_ASSET_NODE = True


def _is_asset(node):
    return node.name().startswith(ASSET_PREFIX)


def _should_hide(node):
    if _is_asset(node):
        return HIDE_ASSET_NODE and not USE_VIEWPORT_STUB
    name = node.name()
    return name.startswith(HIDE_PREFIXES) or name.endswith(HIDE_SUFFIXES)


def _asset_containers():
    obj = hou.node("/obj")
    if obj is None:
        return []
    return [n for n in obj.children() if _is_asset(n)]


def _generator_sop(container):
    """The HDA node Houdini Engine instantiated inside the container."""
    for c in container.children():
        if c.name() == STUB_NAME:
            continue
        if c.type().name().startswith(ASSET_PREFIX):
            return c
    return None


def _ensure_stub(container):
    """Create the cheap display SOP and make sure it holds the display flag.

    Called the moment Houdini Engine creates the container - at that point the
    container is still empty, so the stub is the first node in it and keeps the
    display flag when HAPI creates the HDA next to it.
    """
    stub = container.node(STUB_NAME)
    if stub is None:
        stub = container.createNode("null", STUB_NAME)
        stub.setPosition(hou.Vector2(-4.0, 0.0))
        try:
            stub.setColor(hou.Color((0.9, 0.45, 0.1)))
            stub.setComment(
                "Viewport stub. Holds the display flag so Houdini never cooks\n"
                "the generator for the viewport. Unreal reads the HDA node\n"
                "directly and does not care about this flag.")
            stub.setGenericFlag(hou.nodeFlag.DisplayComment, True)
        except Exception:
            pass
    if not stub.isDisplayFlagSet():
        stub.setDisplayFlag(True)
    if not container.isDisplayFlagSet():
        # Unreal only gathers outputs from a VISIBLE container.
        container.setDisplayFlag(True)
    return stub


def _flag_guard(node=None, event_type=None, **kwargs):
    """Give the display flag back to the stub the instant something takes it.

    04-09-2026, measured: creating the stub at instantiation is NOT enough.
    Something on the Houdini Engine side puts the display flag back on the HDA
    later (Session Sync mirrors the Unreal asset into the viewport), and from
    that moment every Unreal cook is followed by a viewport cook of the same
    node - `buildgen1.cookCount()` was 4 for two cooks Unreal actually asked
    for. Only a FlagChanged watchdog holds the flag.
    """
    if getattr(hou.session, "_bg_flag_busy", False):
        return
    if getattr(hou.session, "_bg_guard_off", False):
        return
    try:
        if node is not None and node.isDisplayFlagSet():
            hou.session._bg_flag_busy = True
            stub = node.parent().node(STUB_NAME)
            if stub is not None:
                stub.setDisplayFlag(True)
    except Exception:
        pass
    finally:
        hou.session._bg_flag_busy = False


def _poll_guard():
    """Idle-loop watchdog: hand the display flag back to the stub.

    04-09-2026 cold test: the FlagChanged callback above NEVER fired when
    Houdini Engine put the display flag back on the HDA - HAPI sets the flag
    without going through the node event system (or the callback is swallowed
    while the node is cooking). The flag ended up on the HDA, the viewport
    cooked the whole floor, Unreal saw the cook count change and asked for
    another cook: the loop that can only be broken by killing Houdini.

    hou.ui.addEventLoopCallback runs on every idle pass of the interactive
    session, which is exactly the < 1 s window between "Unreal finished
    building outputs" and "the viewport starts cooking". It costs a handful of
    flag reads per tick.
    """
    st = hou.session
    if getattr(st, "_bg_guard_off", False):
        return
    tick = getattr(st, "_bg_poll_tick", 0) + 1
    st._bg_poll_tick = tick
    cached = getattr(st, "_bg_poll_cache", None)
    if cached is None or tick % 50 == 0:
        cached = []
        try:
            for c in _asset_containers():
                stub = c.node(STUB_NAME)
                if stub is None:
                    stub = _ensure_stub(c)
                cached.append((c, stub))
        except Exception:
            cached = []
        st._bg_poll_cache = cached
    try:
        for container, stub in cached:
            if not stub.isDisplayFlagSet():
                stub.setDisplayFlag(True)
            if not container.isDisplayFlagSet():
                container.setDisplayFlag(True)
    except Exception:
        # a node was deleted under us - rebuild the cache on the next tick
        st._bg_poll_cache = None


def _install_poll():
    if not hou.isUIAvailable():
        return
    old = getattr(hou.session, "hengine_poll_cb", None)
    if old is not None:
        try:
            hou.ui.removeEventLoopCallback(old)
        except Exception:
            pass
    hou.session._bg_poll_cache = None
    hou.session._bg_guard_off = False
    try:
        hou.ui.addEventLoopCallback(_poll_guard)
        hou.session.hengine_poll_cb = _poll_guard
    except Exception:
        hou.session.hengine_poll_cb = None


def _guard_generator(container):
    """Attach the FlagChanged watchdog to the HDA node inside the container."""
    gen = _generator_sop(container)
    if gen is None:
        return
    guarded = getattr(hou.session, "hengine_guarded", None)
    if guarded is None:
        guarded = {}
        hou.session.hengine_guarded = guarded
    path = gen.path()
    if path in guarded:
        return
    try:
        gen.addEventCallback((hou.nodeEventType.FlagChanged,), _flag_guard)
        guarded[path] = _flag_guard
    except Exception:
        pass


def _unguard_all():
    guarded = getattr(hou.session, "hengine_guarded", None) or {}
    for path, cb in list(guarded.items()):
        n = hou.node(path)
        if n is not None:
            try:
                n.removeEventCallback((hou.nodeEventType.FlagChanged,), cb)
            except Exception:
                pass
    hou.session.hengine_guarded = {}


def _on_asset_child(node=None, event_type=None, child_node=None, **kwargs):
    """Runs when HAPI adds a node inside the asset container."""
    if not USE_VIEWPORT_STUB or node is None:
        return
    if child_node is not None and child_node.name() == STUB_NAME:
        return
    try:
        stub = node.node(STUB_NAME)
        if stub is None:
            _ensure_stub(node)
        elif not stub.isDisplayFlagSet():
            # HAPI just created a node that grabbed the display flag - take it back.
            stub.setDisplayFlag(True)
        _guard_generator(node)
    except Exception:
        pass


def _watch_container(container):
    watched = getattr(hou.session, "hengine_watched", None)
    if watched is None:
        watched = {}
        hou.session.hengine_watched = watched
    path = container.path()
    if path in watched:
        return
    try:
        container.addEventCallback((hou.nodeEventType.ChildCreated,), _on_asset_child)
        watched[path] = _on_asset_child
    except Exception:
        pass


def _unwatch_all():
    watched = getattr(hou.session, "hengine_watched", None) or {}
    for path, cb in list(watched.items()):
        n = hou.node(path)
        if n is not None:
            try:
                n.removeEventCallback((hou.nodeEventType.ChildCreated,), cb)
            except Exception:
                pass
    hou.session.hengine_watched = {}


def _handle_new_node(node=None, event_type=None, child_node=None, **kwargs):
    n = child_node
    if n is None:
        return
    try:
        if _is_asset(n):
            if USE_VIEWPORT_STUB:
                if not n.isDisplayFlagSet():
                    n.setDisplayFlag(True)
                _ensure_stub(n)
                _watch_container(n)
                _guard_generator(n)
            elif HIDE_ASSET_NODE and n.isDisplayFlagSet():
                n.setDisplayFlag(False)
        elif _should_hide(n) and n.isDisplayFlagSet():
            n.setDisplayFlag(False)
    except Exception:
        pass


def _set_asset_display(state):
    """Legacy: turn the container's display flag on/off (two-pass workflow)."""
    touched = []
    for n in _asset_containers():
        if n.isDisplayFlagSet() != state:
            n.setDisplayFlag(state)
            touched.append(n.name())
    return touched


def show_asset():
    """Put the generator itself in the viewport.

    WARNING: the next viewport update cooks the whole floor (~2.5 min), and
    while it is on display every Unreal cook is computed twice. Use it to look
    at the result, then press the button again.
    """
    if not USE_VIEWPORT_STUB:
        return _set_asset_display(True)
    # the idle watchdog would snatch the flag straight back
    hou.session._bg_guard_off = True
    touched = []
    for c in _asset_containers():
        c.setDisplayFlag(True)
        gen = _generator_sop(c)
        if gen is not None:
            gen.setDisplayFlag(True)
            touched.append(gen.path())
    return touched


def hide_asset():
    """Back to the stub: the viewport draws nothing, Unreal still gets everything."""
    if not USE_VIEWPORT_STUB:
        return _set_asset_display(False)
    hou.session._bg_guard_off = False
    hou.session._bg_poll_cache = None
    touched = []
    for c in _asset_containers():
        c.setDisplayFlag(True)
        touched.append(_ensure_stub(c).path())
    return touched


def install():
    # HARS - the headless server Unreal starts for "Create Session" - loads this
    # same file. There is no viewport there, so there is nothing to protect, and
    # touching flags is actively harmful: Unreal gathers outputs ONLY from
    # visible OBJ nodes, so a hidden SM_BLDG block cooks fine, reports no error,
    # and leaves nothing behind. Only the interactive session needs this.
    # Confirmed 03-09-2026: HARS loads this file with ui=False.
    if not hou.isUIAvailable():
        return

    obj = hou.node("/obj")
    if obj is None:
        return
    # drop previously installed callbacks so reloading a scene never stacks them
    old = getattr(hou.session, "hengine_hide_cb", None)
    if old is not None:
        try:
            obj.removeEventCallback((hou.nodeEventType.ChildCreated,), old)
        except Exception:
            pass
    _unwatch_all()
    _unguard_all()

    obj.addEventCallback((hou.nodeEventType.ChildCreated,), _handle_new_node)
    hou.session.hengine_hide_cb = _handle_new_node
    # second line of defence: FlagChanged did not fire in the 04-09 cold test
    _install_poll()
    # expose the helpers to the shelf button / python shell
    hou.session.hengine_show_asset = show_asset
    hou.session.hengine_hide_asset = hide_asset
    # also fix up anything already sitting in the scene
    for n in obj.children():
        try:
            if _is_asset(n):
                if USE_VIEWPORT_STUB:
                    if not n.isDisplayFlagSet():
                        n.setDisplayFlag(True)
                    _ensure_stub(n)
                    _watch_container(n)
                    _guard_generator(n)
                elif HIDE_ASSET_NODE and n.isDisplayFlagSet():
                    n.setDisplayFlag(False)
            elif _should_hide(n) and n.isDisplayFlagSet():
                n.setDisplayFlag(False)
        except Exception:
            pass


install()
