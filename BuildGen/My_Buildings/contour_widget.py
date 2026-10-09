# -*- coding: utf-8 -*-
"""
contour_widget.py - движок отчёта для Editor Utility Widget.

Лежит в <проект>/Content/Python, поэтому импортируется по имени.

Вызов из виджета (нода "Execute Python Command (Advanced)",
режим Evaluate Statement):

    __import__("importlib").reload(__import__("contour_widget")).run(r"/Game/My_Buildings")

Возвращает текст отчёта: таблица блоков по этажам + таблица сторон контура.
"""

import math
import unreal

WIDTH_AXIS = "y"    # ось ширины блока у кита SFJ


class Report(str):
    """Строка, которую нода Python отдаёт в Blueprint без экранирования.

    Execute Python Command (Advanced) прогоняет результат через PyObject_Repr.
    У обычной строки repr добавил бы кавычки и превратил переводы строк в \\n,
    поэтому repr переопределён на сам текст.
    """

    def __repr__(self):
        return str(self)


# ------------------------------------------------------------------- блоки
def mesh_box(m):
    try:
        b = m.get_bounding_box()
        dims = (b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z)
        return dims, b.min.y, b.max.y, (b.min.x + b.max.x) / 2.0
    except Exception:
        pass
    try:
        bs = m.get_bounds()
        e = bs.box_extent
        o = bs.origin
        return (e.x * 2.0, e.y * 2.0, e.z * 2.0), o.y - e.y, o.y + e.y, o.x
    except Exception:
        return None, None, None, 0.0


def width_of(dims, ymin):
    """Шаг блока: от пивота до дальнего края. Генератор ставит блоки по пивотам."""
    if ymin is not None and abs(ymin) > 0.01:
        return abs(ymin)
    if not dims:
        return 0.0
    if WIDTH_AXIS == "x":
        return dims[0]
    if WIDTH_AXIS == "y":
        return dims[1]
    return max(dims[0], dims[1])


def scan_kit(kit_root):
    """{ подпапка: [ (имя, ширина) ] } - в порядке имён папок."""
    kit = {}
    try:
        paths = unreal.EditorAssetLibrary.list_assets(kit_root, recursive=True,
                                                      include_folder=False)
    except Exception:
        return None
    for p in paths:
        clean = p.split(".")[0]
        rel = clean[len(kit_root):].lstrip("/")
        parts = rel.split("/")
        folder = parts[0] if len(parts) > 1 else "(корень)"
        name = parts[-1]
        try:
            a = unreal.EditorAssetLibrary.load_asset(clean)
        except Exception:
            continue
        if not isinstance(a, unreal.StaticMesh):
            continue
        dims, ymin, _, _ = mesh_box(a)
        kit.setdefault(folder, []).append((name, width_of(dims, ymin)))
    for f in kit:
        kit[f].sort(key=lambda t: t[0])
    return kit


# ------------------------------------------------------------------ контур
def selected_actors():
    try:
        ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        return list(ss.get_selected_level_actors())
    except Exception:
        return list(unreal.EditorLevelLibrary.get_selected_level_actors())


def all_actors():
    try:
        ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        return list(ss.get_all_level_actors())
    except Exception:
        return list(unreal.EditorLevelLibrary.get_all_level_actors())


def splines_of(actor):
    try:
        return list(actor.get_components_by_class(unreal.SplineComponent))
    except Exception:
        return []


def find_spline():
    for a in selected_actors():
        c = splines_of(a)
        if c:
            return a, c[0], None
    found = [(a, splines_of(a)[0]) for a in all_actors() if splines_of(a)]
    if len(found) == 1:
        return found[0][0], found[0][1], None
    if not found:
        return None, None, "no actor with a Spline Component in the level."
    names = ", ".join(a.get_actor_label() for a, _ in found)
    return None, None, "several splines found - select the actor you need: %s" % names


def dist_xy(a, b):
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)


def turn_deg(p_prev, p_cur, p_next):
    a1 = math.atan2(p_cur.y - p_prev.y, p_cur.x - p_prev.x)
    a2 = math.atan2(p_next.y - p_cur.y, p_next.x - p_cur.x)
    t = math.degrees(a2 - a1)
    while t > 180.0:
        t -= 360.0
    while t <= -180.0:
        t += 360.0
    return t


# ------------------------------------------------------------------ отчёт
def run(kit_root="/Game/My_Buildings"):
    L = []

    def add(s=""):
        L.append(s)

    kit_root = (kit_root or "").strip().rstrip("/")
    if not kit_root:
        kit_root = "/Game/My_Buildings"

    add("KIT: %s" % kit_root)
    add("")

    # ---- блоки по этажам
    kit = scan_kit(kit_root)
    if kit is None:
        add("!! Cannot read that folder. The path must start with /Game/")
    elif not kit:
        add("!! No Static Mesh found in that folder.")
    else:
        add("    %-46s %9s" % ("BLOCK", "WIDTH"))
        add("")
        for folder in sorted(kit.keys()):
            items = kit[folder]
            add("[%s]   blocks: %d" % (folder, len(items)))
            for name, w in items:
                add("    %-46s %9.1f" % (name, w))
            add("")

    # ---- стороны контура
    actor, spline, err = find_spline()
    if err:
        add("SIDES: %s" % err)
        return Report("\n".join(L))

    n = spline.get_number_of_spline_points()
    closed = spline.is_closed_loop()
    pts = [spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
           for i in range(n)]

    bad = []
    for i in range(n):
        try:
            t = str(spline.get_spline_point_type(i))
            t = t.split(".")[-1].split(":")[0].strip().strip(">").strip().upper()
        except Exception:
            t = "?"
        if t not in ("LINEAR", "?"):
            bad.append(i)

    n_sides = n if closed else n - 1
    per = sum(dist_xy(pts[i], pts[(i + 1) % n]) for i in range(n_sides))

    add("SIDES   spline: %s   points: %d   Closed Loop: %s"
        % (actor.get_actor_label(), n, "yes" if closed else "NO"))
    add("perimeter: %.1f cm (%.2f m)" % (per, per / 100.0))
    if not closed:
        add("!! Closed Loop is off - the closing side is not counted.")
    if bad:
        add("!! Points not set to Linear: %s - lengths measured as straight segments."
            % ", ".join(str(i) for i in bad))
    add("")
    add("    %-8s %14s %16s" % ("SIDE", "LENGTH, cm", "BEND ANGLE"))
    for i in range(n_sides):
        a = pts[i]
        b = pts[(i + 1) % n]
        if closed or (i + 2) <= (n - 1):
            ang = "%+.2f" % turn_deg(a, b, pts[(i + 2) % n])
        else:
            ang = "-"
        add("    %-8d %14.1f %16s" % (i + 1, dist_xy(a, b), ang))

    return Report("\n".join(L))


# =====================================================================
#                        CONTOUR PLANNER (solver)
# =====================================================================
# The recipe is plain text, one line per side:
#
#     1: CL_0, W_1, W_2+N, EN
#     2: CL_0, CL_0, W_1+N
#     3: CL_0
#
# Names are the actor labels in the Outliner. The token ending in _0
# (or the first token, if none does) is the bending corner block of that
# side - it goes into Corner Source. "+N" marks a block whose number of
# copies the widget works out. Any number of lines: the number of sides
# is never hard-coded. The last line - a lone corner - is the lock.
#
# HOW THE BUILDING REALLY WALKS THE CONTOUR
#   * Straight blocks step by their pivot width, one after another.
#   * A corner block is BENT by Houdini's bend SOP over its whole length,
#     so it does not step by its width: its straight advance is the chord
#     of an arc, w * sin(A/2)/(A/2), and it leaves at an angle A.
#   * The FIRST block of the building is straight - there is no corner
#     block at point 1. So a building with N sides has N-1 bends, and the
#     lock must run out exactly along side 1: the two are collinear.

COPIES_MEANS_TOTAL = True   # measured 08-09-2026: Copies = how many blocks in total,
#                             not how many extra on top of the one in the slot


# ------------------------------------------------------------- recipe
def split_offset(token):
    """'W_2+N@0.085' -> ('W_2+N', 8.5). The offset is written in Houdini units
    (the same number you type into the generator) and used here in cm."""
    t = token.strip()
    off = 0.0
    if "@" in t:
        t, o = t.split("@", 1)
        try:
            off = float(o.strip().replace(",", ".")) * 100.0
        except ValueError:
            off = 0.0
        t = t.strip()
    return t, off


def base_name(token):
    """'W_2+N' -> 'W_2'. The +N is recipe syntax, not part of the name."""
    t = split_offset(token)[0]
    up = t.upper().replace(" ", "")
    if up.endswith("+N"):
        return t[:t.upper().rfind("+N")].strip()
    return t.strip()


def parse_recipe(text):
    """Text -> [ {label, corner:{name}, blocks:[{name, rep}]} ]."""
    sides = []
    for raw in (text or "").replace("\r", "\n").split("\n"):
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        if ":" in ln:
            head, body = ln.split(":", 1)
        else:
            head, body = "", ln
        toks = [t.strip() for t in body.replace(";", ",").split(",") if t.strip()]
        if not toks:
            continue
        blocks = []
        for t in toks:
            nm, off = split_offset(t)
            rep = nm.upper().replace(" ", "").endswith("+N")
            blocks.append({"name": nm, "rep": rep, "off": off})
        ci = 0
        for k, b in enumerate(blocks):
            if base_name(b["name"]).split("_")[-1] == "0":
                ci = k
                break
        corner = blocks.pop(ci)
        sides.append({"label": (head.strip() or str(len(sides) + 1)),
                      "corner": corner, "blocks": blocks})
    return sides


# ------------------------------------------------------- block widths
TEMP_ROOT = "/Game/HoudiniEngine/Temp"


def baked_mesh_of(a):
    """The Static Mesh a block HDA has already produced.

    A block dropped into the viewport shows a proxy, and a proxy's bounds carry
    extra hull - but the real mesh is already sitting in HoudiniEngine/Temp under
    the block's own name. Take it from there instead of measuring the proxy.
    """
    name = None
    try:
        for c in a.get_components_by_class(unreal.SceneComponent):
            cls = c.get_class().get_name()
            if "HoudiniAssetComponent" not in cls:
                continue
            for prop in ("houdini_asset", "HoudiniAsset"):
                try:
                    hda = c.get_editor_property(prop)
                except Exception:
                    hda = None
                if hda:
                    name = hda.get_name()
                    break
            if name:
                break
    except Exception:
        pass
    if not name:
        return None
    try:
        paths = unreal.EditorAssetLibrary.list_assets("%s/%s" % (TEMP_ROOT, name),
                                                      recursive=True, include_folder=False)
    except Exception:
        return None
    for p in paths:
        try:
            obj = unreal.EditorAssetLibrary.load_asset(p.split(".")[0])
        except Exception:
            continue
        if isinstance(obj, unreal.StaticMesh):
            return obj
    return None


def actor_mesh_width(a):
    """Step width and depth of one block actor, in cm.

    Returns (width, axis, source, note). "axis" is how far the block's bounding
    box centre sits from its pivot across the wall: the generator bends around
    exactly that line ((XMIN+XMAX)/2 in its own words), so the pivot rides the
    outer radius and the corner advances the contour further than a plain arc.
    """
    meshes = []
    try:
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            try:
                if c.static_mesh:
                    meshes.append((c.static_mesh, "mesh"))
            except Exception:
                pass
    except Exception:
        pass
    baked = baked_mesh_of(a)
    if baked is not None:
        meshes.append((baked, "baked"))
    for m, src in meshes:
        dims, ymin, _, xc = mesh_box(m)
        w = width_of(dims, ymin)
        if w > 0.01:
            return w, abs(xc or 0.0), src, ""
    note = ""
    try:
        rot = a.get_actor_rotation()
        if abs(rot.yaw) > 0.01 or abs(rot.pitch) > 0.01 or abs(rot.roll) > 0.01:
            note = "actor is rotated, width taken from world bounds may be off"
    except Exception:
        pass
    try:
        loc = a.get_actor_location()
        origin, extent = a.get_actor_bounds(False)
        axis = abs(origin.x - loc.x)
        ymin = (origin.y - extent.y) - loc.y
        if abs(ymin) > 0.01:
            return abs(ymin), axis, "bounds", note
        return extent.y * 2.0, axis, "bounds", note
    except Exception:
        return 0.0, 0.0, "none", note


def actor_widths(names):
    """{recipe name: (label, width, source)} + missing + unmeasured + notes."""
    want = {}
    for n in names:
        want[base_name(n).lower()] = None
        want[n.strip().lower()] = None
    seen = {}
    for a in all_actors():
        k = a.get_actor_label().strip().lower()
        if k in want:
            seen[k] = a
    out, missing, unmeasured, notes = {}, [], [], []
    for n in names:
        a = seen.get(base_name(n).lower()) or seen.get(n.strip().lower())
        if a is None:
            missing.append(n)
            continue
        w, depth, src, note = actor_mesh_width(a)
        # A block narrower than 10 cm is not a block: the actor has no geometry
        # right now - typically Houdini was restarted and the block HDAs lost
        # their nodes. Refuse, instead of filling a wall with 10000 slivers.
        if w < 10.0:
            unmeasured.append(a.get_actor_label())
            continue
        if note:
            notes.append("%s: %s" % (a.get_actor_label(), note))
        out[n] = (a.get_actor_label(), w, src, depth)
    return out, sorted(set(missing)), sorted(set(unmeasured)), sorted(set(notes))


# --------------------------------------------------------- arithmetic
def side_parts(side, W):
    """(corner width, corner depth, fixed straight length, [steps of +N blocks]).

    A block with an offset steps by width - offset: the offset pulls the block
    back toward the one before it. Measured on the built floor, exact to 0.5 cm.
    """
    corner = W[side["corner"]["name"]][1] - side["corner"].get("off", 0.0)
    corner_axis = W[side["corner"]["name"]][3]
    fixed = 0.0
    steps = []
    for b in side["blocks"]:
        w = W[b["name"]][1] - b.get("off", 0.0)
        fixed += w
        if b["rep"]:
            steps.append(w)
    return corner, corner_axis, fixed, steps


def counts_for(fixed, steps, target):
    """Copies spread evenly over the +N blocks, round-robin, nearest fit."""
    steps = [w for w in steps if w > 10.0]     # nothing sane steps by 10 cm
    n = [0] * len(steps)
    L = fixed
    if not steps:
        return n, L
    i, guard = 0, 0
    while guard < 20000:
        guard += 1
        placed = False
        for j in range(len(steps)):
            k = (i + j) % len(steps)
            w = steps[k]
            if L + w <= target + w * 0.5:
                L += w
                n[k] += 1
                i = k + 1
                placed = True
                break
        if not placed:
            break
    return n, L


def wrap_angle(a):
    """Any angle -> the same turn expressed within (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def chord_of(w, a, u=0.0):
    """Straight advance of a corner block of width w bent by angle a (radians).

    Houdini's bend SOP turns the block's whole length into an arc - but the
    axis it bends around is sunk half the block's thickness inside it, so the
    pivot line rides the OUTER radius and travels further than the neutral arc:

        advance = 2 * (w / |a| + u) * sin(|a| / 2),   u = pivot-to-axis

    and the advance runs at half the turn. Checked against three corners of a
    built floor: predicted and measured agree to the millimetre.
    """
    if abs(a) < 1e-9:
        return w
    h = abs(a) / 2.0
    return 2.0 * (w / abs(a) + u) * math.sin(h)


def chain_vectors(th, corner_w, straight_w, corner_u=None):
    """Vector of every side: bent corner (chord) + straight blocks after it.

    th[i] is the direction of side i; the lock's direction equals side 1's.
    """
    n = len(corner_w)
    U = corner_u or [0.0] * n
    out = []
    for i in range(n):
        if i == 0:
            ln = corner_w[0] + straight_w[0]          # first block is straight
            out.append((ln * math.cos(th[0]), ln * math.sin(th[0])))
        else:
            a = wrap_angle(th[i] - th[i - 1])
            c = chord_of(corner_w[i], a, U[i])
            d = th[i - 1] + a / 2.0                    # chord runs at half the turn
            out.append((c * math.cos(d) + straight_w[i] * math.cos(th[i]),
                        c * math.sin(d) + straight_w[i] * math.sin(th[i])))
    return out


def fit_directions(corner_w, straight_w, V, corner_u=None):
    """Recover the WALL directions of a drawn contour.

    A spline point sits where the bent corner block starts, so the straight
    line from point to point is not the wall direction: it is the arc's chord
    plus the straight blocks after it. Peel the chord off and what is left
    points along the wall. Done as a short fixed-point loop - and it lands
    exactly on the previous answer for a contour this widget wrote itself,
    so pressing the button twice changes nothing.
    """
    n = len(V)
    U = corner_u or [0.0] * n
    th = [math.atan2(v[1], v[0]) for v in V]
    for _ in range(60):
        mx = 0.0
        for i in range(n):
            if i == 0:
                new_th = math.atan2(V[0][1], V[0][0])
            else:
                a = wrap_angle(th[i] - th[i - 1])
                c = chord_of(corner_w[i], a, U[i])
                d = th[i - 1] + a / 2.0
                rx = V[i][0] - c * math.cos(d)
                ry = V[i][1] - c * math.sin(d)
                if math.hypot(rx, ry) < 1e-6:      # lock side: corner only
                    new_th = th[i]
                else:
                    new_th = math.atan2(ry, rx)
            mx = max(mx, abs(wrap_angle(new_th - th[i])))
            th[i] = new_th
        if mx < 1e-12:
            break
    return th


def close_contour(corner_w, straight_w, th0, corner_u=None):
    """Turn the sides just enough to close the loop, arcs included.

    Block widths cannot change, so the lock is forced home with angles.
    Unknowns are the side directions; the lock is tied to side 1 because the
    building's first block is straight and cannot bend. Every step is the
    smallest one that removes the gap, so the correction lands on all sides
    a little instead of on one side a lot.
    """
    n = len(corner_w)
    # Side 1 is nailed down: its point is the anchor and its direction is the
    # anchor too, otherwise the whole building would swing a little every time
    # the widget is run. Free angles are sides 2..N-1; the lock follows side 1.
    free = list(range(1, n - 1))
    if len(free) < 2:                      # too few sides - let side 1 turn too
        free = list(range(0, n - 1))
    m = len(free)
    x = [th0[k] for k in free]

    def full(xv):
        th = list(th0[:n])
        for k, idx in enumerate(free):
            th[idx] = xv[k]
        th[n - 1] = th[0]                  # the lock runs out along side 1
        return th

    def resid(xv):
        v = chain_vectors(full(xv), corner_w, straight_w, corner_u)
        return [sum(p[0] for p in v), sum(p[1] for p in v)]

    for _ in range(300):
        r = resid(x)
        if abs(r[0]) < 1e-6 and abs(r[1]) < 1e-6:
            return full(x), (r[0], r[1]), True
        h = 1e-6
        J = [[0.0] * m, [0.0] * m]
        for k in range(m):
            x2 = list(x)
            x2[k] += h
            r2 = resid(x2)
            J[0][k] = (r2[0] - r[0]) / h
            J[1][k] = (r2[1] - r[1]) / h
        a = sum(J[0][k] * J[0][k] for k in range(m))
        b = sum(J[0][k] * J[1][k] for k in range(m))
        d = sum(J[1][k] * J[1][k] for k in range(m))
        det = a * d - b * b
        if abs(det) < 1e-18:
            break
        l0 = (-r[0] * d + r[1] * b) / det
        l1 = (-r[1] * a + r[0] * b) / det
        for k in range(m):
            x[k] += J[0][k] * l0 + J[1][k] * l1
    r = resid(x)
    return full(x), (r[0], r[1]), (abs(r[0]) < 1e-3 and abs(r[1]) < 1e-3)


def apply_points(actor, spline, pts):
    try:
        actor.modify()
    except Exception:
        pass
    for i, p in enumerate(pts):
        spline.set_location_at_spline_point(i, p, unreal.SplineCoordinateSpace.WORLD, False)
    try:
        spline.update_spline()
    except Exception:
        pass
    # the level is NOT saved here - saving stays a manual step


def norm_deg(a):
    while a > 180.0:
        a -= 360.0
    while a <= -180.0:
        a += 360.0
    return a


# -------------------------------------------------------------- entry
def plan(recipe_text, apply_to_level=False, kit_root="/Game/My_Buildings"):
    """Recipe + spline -> copies per block and a contour that closes."""
    L = []

    def add(s=""):
        L.append(s)

    # a line "axis: 0.5193" pins the bend axis by hand, in Houdini units.
    # Needed while the blocks are proxies: their actor bounds carry extra hull
    # and the measured centre comes out wrong.
    axis_override, kept = None, []
    for ln in (recipe_text or "").replace("\r", "\n").split("\n"):
        if ln.strip().lower().startswith("axis:"):
            try:
                axis_override = float(ln.split(":", 1)[1].strip().replace(",", ".")) * 100.0
            except ValueError:
                pass
        else:
            kept.append(ln)
    recipe_text = "\n".join(kept)

    sides = parse_recipe(recipe_text)
    if not sides:
        return Report("Recipe is empty. Line format:   1: CL_0, W_1, W_2+N, EN")

    actor, spline, err = find_spline()
    if err:
        return Report("SIDES: %s" % err)

    n_pt = spline.get_number_of_spline_points()
    closed = spline.is_closed_loop()
    if not closed:
        add("!! Closed Loop is off on the spline - the loop must be closed.")
        add("")
    if len(sides) != n_pt:
        add("!! Recipe lines: %d, spline points: %d. They must match." % (len(sides), n_pt))
        add("   Spline left untouched.")
        return Report("\n".join(L))

    names = []
    for s in sides:
        names.append(s["corner"]["name"])
        names += [b["name"] for b in s["blocks"]]
    W, missing, unmeasured, notes = actor_widths(names)
    if missing:
        add("!! No actor in the Outliner with these labels: %s" % ", ".join(missing))
        add("   Rename the blocks in the Outliner exactly as in the recipe.")
        return Report("\n".join(L))
    if unmeasured:
        add("!! Could not measure these blocks: %s" % ", ".join(unmeasured))
        add("   They carry no geometry right now. If Houdini has just been")
        add("   restarted, recook the block HDAs first, then press CALCULATE PLAN.")
        return Report("\n".join(L))

    P = [spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
         for i in range(n_pt)]
    tgt = [dist_xy(P[i], P[(i + 1) % n_pt]) for i in range(n_pt)]
    th0 = [math.atan2(P[(i + 1) % n_pt].y - P[i].y, P[(i + 1) % n_pt].x - P[i].x)
           for i in range(n_pt)]

    # how many copies: measure against the contour as drawn, with the corner
    # already counted as a chord at the drawn turn
    corner_w, corner_u, straight_w, cnts = [], [], [], []
    for i, s in enumerate(sides):
        cw, caxis, fixed, steps = side_parts(s, W)
        a0 = 0.0 if i == 0 else wrap_angle(th0[i] - th0[i - 1])
        cu = caxis if axis_override is None else axis_override
        c, _ = counts_for(chord_of(cw, a0, cu) + fixed, steps, tgt[i])
        cnts.append(c)
        corner_w.append(cw)
        corner_u.append(caxis if axis_override is None else axis_override)
        straight_w.append(fixed + sum(c[k] * steps[k] for k in range(len(steps))))

    drawn_vec = [(P[(i + 1) % n_pt].x - P[i].x, P[(i + 1) % n_pt].y - P[i].y)
                 for i in range(n_pt)]
    th_fit = fit_directions(corner_w, straight_w, drawn_vec, corner_u)
    th, resid, ok = close_contour(corner_w, straight_w, th_fit, corner_u)
    vecs = chain_vectors(th, corner_w, straight_w, corner_u)

    new = [P[0]]
    for i in range(n_pt - 1):
        p = new[-1]
        new.append(unreal.Vector(p.x + vecs[i][0], p.y + vecs[i][1], P[i + 1].z))

    add("CONTOUR PLAN    spline: %s    sides: %d" % (actor.get_actor_label(), n_pt))
    add("")
    offs = {}
    for s in sides:
        for b in [s["corner"]] + s["blocks"]:
            if b.get("off", 0.0):
                offs[b["name"]] = b["off"]
    add("BLOCK WIDTHS (step from the pivot):")
    for n in sorted(W.keys(), key=lambda x: x.lower()):
        lab, w, src, depth = W[n]
        o = offs.get(n, 0.0)
        if o:
            add("    %-28s %9.1f   %s   offset %.1f -> step %.1f" % (lab, w, src, o, w - o))
        else:
            add("    %-28s %9.1f   %s" % (lab, w, src))
    add("    corner bend axis: %.1f from the pivot  (source: %s)"
        % (corner_u[0], "recipe" if axis_override is not None
           else W[sides[0]["corner"]["name"]][2]))
    for t in notes:
        add("    !! %s" % t)
    add("")
    add("    %-6s %-40s %10s %10s %8s" % ("SIDE", "BLOCKS (copies)", "DRAWN", "FITTED", "DIFF"))
    for i, s in enumerate(sides):
        parts = [base_name(s["corner"]["name"])]
        k = 0
        for b in s["blocks"]:
            if b["rep"]:
                parts.append("%s x%d" % (base_name(b["name"]), cnts[i][k] + 1))
                k += 1
            else:
                parts.append(b["name"])
        fitted = math.sqrt(vecs[i][0] ** 2 + vecs[i][1] ** 2)
        add("    %-6s %-40s %10.1f %10.1f %+8.1f"
            % (s["label"], ", ".join(parts), tgt[i], fitted, fitted - tgt[i]))
    add("")
    add("COPIES to type into the generator (Copies of the +N block):")
    any_rep = False
    for i, s in enumerate(sides):
        k, slot = 0, 0
        for b in s["blocks"]:
            slot += 1
            if b["rep"]:
                any_rep = True
                add("    side %-4s  slot %-3d  %-24s  Copies = %d"
                    % (s["label"], slot, base_name(b["name"]),
                       cnts[i][k] + (1 if COPIES_MEANS_TOTAL else 0)))
                k += 1
    if not any_rep:
        add("    (no +N blocks in the recipe)")
    add("")
    add("BEND ANGLE to type into the generator:")
    add("    side %-4s  %8.2f" % (sides[0]["label"], 0.0))
    for i in range(1, n_pt):
        add("    side %-4s  %8.2f"
            % (sides[i]["label"], norm_deg(math.degrees(wrap_angle(th[i] - th[i - 1])))))
    add("")
    add("SPLINE POINTS (point 1 is the anchor, it never moves):")
    add("    %-6s %12s %12s %12s" % ("POINT", "SHIFT, cm", "X", "Y"))
    for i in range(n_pt):
        add("    %-6d %12.1f %12.1f %12.1f" % (i + 1, dist_xy(P[i], new[i]), new[i].x, new[i].y))
    add("")

    if not ok:
        add("!! The loop did not close: %.2f x %.2f cm left. Spline untouched." % resid)
        return Report("\n".join(L))

    add("loop closed, error %.4f x %.4f cm" % resid)
    if apply_to_level:
        apply_points(actor, spline, new)
        add("SPLINE UPDATED in the level. Save the level yourself when it looks right.")
    else:
        add("(spline untouched - press APPLY TO SPLINE to let the widget move the points)")

    return Report("\n".join(L))
