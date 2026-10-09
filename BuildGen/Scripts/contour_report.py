# -*- coding: utf-8 -*-
"""
contour_report.py - замер контура сплайна + габариты кита блоков.

Запуск в Unreal: Output Log -> поле снизу переключить в режим Cmd -> ввести:
    py "<папка генератора>/Scripts/contour_report.py"

Отчёт печатается в Output Log И пишется в файл OUT_FILE.
"""

import math
import os
import unreal

# ---------------------------------------------------------------- настройки
KIT_ROOT   = "/Game/My_Buildings"          # родительская папка кита
FLOOR      = "01_First_Floor"              # подпапка, по которой считаем подбор
OUT_FILE   = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "Logs", "contour_report.txt")
WIDTH_AXIS = "y"                           # "auto" | "x" | "y"  (кит SFJ: ширина = Y)

# Чем считать ширину блока - ШАГ, с которым генератор ставит блоки вдоль стороны:
#   "bbox"  - весь габарит по оси ширины (у Wall_01 это 493.1)
#   "pivot" - от пивота до дальнего края, |Ymin| (у Wall_01 это 405.9);
#             разница 87.3 - это нахлёст блока на соседа
WIDTH_MODE = "pivot"

# Из чего состоит сторона ПОМИМО рядовых стен - их ширины вычитаются из длины
# стороны, остаток делится на ширину стены. Правится руками, ролями из role_of():
#   wall, cap_L, cap_R, corner_A (Na1, пивот в углу), corner_B (Nb1, утоплен),
#   entrance.
# ПРОВЕРИТЬ У ALEX'А - пока это предположение по его описанию.
# Na1 на стороне 2+ встречается ДВА раза, в двух разных слотах: один раз как
# загибочный (Corner Source) и один раз как рядовой блок ради отступа.
SIDE_FIXED = {
    1:      ["cap_L", "cap_R", "corner_B"],              # первая сторона
    "rest": ["corner_A", "corner_A", "corner_B"],        # со второй и далее
}

# ------------------------------------------------------------------- вывод
LINES = []


def out(s=""):
    LINES.append(s)
    print(s)


def flush():
    try:
        f = open(OUT_FILE, "w", encoding="utf-8")
        f.write("\n".join(LINES))
        f.close()
        print("[contour_report] отчёт записан: %s" % OUT_FILE)
    except Exception as e:
        print("[contour_report] не смог записать файл: %s" % e)


# ------------------------------------------------------------------ актор
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
            return a, c[0]
    found = []
    for a in all_actors():
        c = splines_of(a)
        if c:
            found.append((a, c[0]))
    if len(found) == 1:
        return found[0]
    if not found:
        out("!! В уровне нет ни одного актора со Spline Component.")
        out("   Сделай BP_ContourSpline (Actor + Spline как корень) и нарисуй контур.")
        return None, None
    out("!! Сплайнов в уровне несколько - выдели нужный актор и запусти снова:")
    for a, _ in found:
        out("     %s" % a.get_actor_label())
    return None, None


# ------------------------------------------------------------- математика
def dist_xy(a, b):
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)


def turn_deg(p_prev, p_cur, p_next):
    """Знаковый угол поворота при переходе с одной стороны на следующую.
    + = поворот влево (против часовой, вид сверху), - = вправо."""
    d1x = p_cur.x - p_prev.x
    d1y = p_cur.y - p_prev.y
    d2x = p_next.x - p_cur.x
    d2y = p_next.y - p_cur.y
    a1 = math.atan2(d1y, d1x)
    a2 = math.atan2(d2y, d2x)
    t = math.degrees(a2 - a1)
    while t > 180.0:
        t -= 360.0
    while t <= -180.0:
        t += 360.0
    return t


def shoelace_area(pts):
    s = 0.0
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        s += a.x * b.y - b.x * a.y
    return s / 2.0


# ------------------------------------------------------------------- кит
def mesh_box(m):
    """(dims, ymin, ymax) - габариты и положение пивота по оси ширины."""
    try:
        b = m.get_bounding_box()
        dims = (b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z)
        return dims, b.min.y, b.max.y
    except Exception:
        pass
    try:
        bs = m.get_bounds()
        e = bs.box_extent
        o = bs.origin
        return (e.x * 2.0, e.y * 2.0, e.z * 2.0), o.y - e.y, o.y + e.y
    except Exception:
        return None, None, None


def role_of(name):
    n = name.upper()
    if "WALLCAP" in n and "_L_" in n:
        return "cap_L"
    if "WALLCAP" in n and "_R_" in n:
        return "cap_R"
    if "WALLCAP" in n:
        return "cap_?"
    if "CORNEREX" in n:
        # Na1 - пивот в самом углу: и загибочный, и рядовой (со 2-й стороны).
        # Nb1 - последний блок стороны, пивот утоплен в стену.
        if "_NA1" in n:
            return "corner_A"
        if "_NB1" in n:
            return "corner_B"
        return "corner"
    if "ENTRANCE" in n:
        return "entrance"
    if "WALL_" in n:
        return "wall"
    return "?"


def scan_kit():
    """{ подпапка: [ {name, path, dims, role} ] }"""
    kit = {}
    try:
        paths = unreal.EditorAssetLibrary.list_assets(KIT_ROOT, recursive=True,
                                                      include_folder=False)
    except Exception as e:
        out("!! Не смог прочитать %s : %s" % (KIT_ROOT, e))
        return kit
    for p in paths:
        clean = p.split(".")[0]
        rel = clean[len(KIT_ROOT):].lstrip("/")
        parts = rel.split("/")
        folder = parts[0] if len(parts) > 1 else "(корень)"
        name = parts[-1]
        try:
            a = unreal.EditorAssetLibrary.load_asset(clean)
        except Exception:
            continue
        if not isinstance(a, unreal.StaticMesh):
            continue
        dims, ymin, ymax = mesh_box(a)
        kit.setdefault(folder, []).append({
            "name": name,
            "path": clean,
            "dims": dims,
            "ymin": ymin,
            "ymax": ymax,
            "role": role_of(name),
        })
    for f in kit:
        kit[f].sort(key=lambda d: d["name"])
    return kit


def width_bbox(d):
    dims = d["dims"]
    if not dims:
        return None
    if WIDTH_AXIS == "x":
        return dims[0]
    if WIDTH_AXIS == "y":
        return dims[1]
    return max(dims[0], dims[1])


def width_pivot(d):
    """Шаг от пивота до дальнего края блока."""
    if d.get("ymin") is None:
        return width_bbox(d)
    return abs(d["ymin"])


def width_of(d):
    if WIDTH_MODE == "pivot":
        return width_pivot(d)
    return width_bbox(d)


# ------------------------------------------------------------------ отчёт
def main():
    out("=" * 78)
    out("ЗАМЕР КОНТУРА  |  кит: %s  |  этаж подбора: %s" % (KIT_ROOT, FLOOR))
    out("=" * 78)

    # ---- кит
    kit = scan_kit()
    out("")
    out("--- ГАБАРИТЫ БЛОКОВ (см) --------------------------------------------")
    for folder in sorted(kit.keys()):
        out("")
        out("  [%s]" % folder)
        out("  %-46s %8s %8s %8s %9s %9s  %s"
            % ("меш", "X", "Y", "Z", "Ymin", "Ymax", "роль"))
        for d in kit[folder]:
            dims = d["dims"]
            if dims:
                out("  %-46s %8.1f %8.1f %8.1f %9.1f %9.1f  %s"
                    % (d["name"], dims[0], dims[1], dims[2],
                       d["ymin"], d["ymax"], d["role"]))
            else:
                out("  %-46s   габариты прочитать не удалось" % d["name"])
    out("")
    out("  Ymin/Ymax - границы блока по оси ширины относительно пивота.")
    out("  Ymin=0 -> пивот с краю блока; Ymin=-Ymax -> пивот по центру.")
    out("  Именно этим отличаются угловые варианты друг от друга.")

    # ---- блоки текущего этажа
    floor = kit.get(FLOOR, [])
    by_role = {}
    for d in floor:
        by_role.setdefault(d["role"], []).append(d)

    def first(role):
        lst = by_role.get(role, [])
        return lst[0] if lst else None

    wall = first("wall")
    cap_l = first("cap_L")
    cap_r = first("cap_R")
    corn_a = first("corner_A") or first("corner")
    corn_b = first("corner_B")

    w_wall = width_of(wall) if wall else None
    w_capl = width_of(cap_l) if cap_l else 0.0
    w_capr = width_of(cap_r) if cap_r else 0.0
    w_corna = width_of(corn_a) if corn_a else 0.0
    w_cornb = width_of(corn_b) if corn_b else 0.0

    out("")
    out("--- ЧТО ВЗЯТО ДЛЯ ПОДБОРА -------------------------------------------")
    pairs = (("стена       ", wall, w_wall),
             ("кэп L       ", cap_l, w_capl),
             ("кэп R       ", cap_r, w_capr),
             ("угол Na1    ", corn_a, w_corna),
             ("угол Nb1    ", corn_b, w_cornb))
    out("  режим ширины: %s" % WIDTH_MODE)
    out("  %s %-46s %10s %10s %10s"
        % ("роль        ", "меш", "габарит", "от пивота", "нахлёст"))
    for label, d, w in pairs:
        if d:
            wb = width_bbox(d)
            wp = width_pivot(d)
            out("  %s %-46s %10.1f %10.1f %10.1f"
                % (label, d["name"], wb, wp, wb - wp))
        else:
            out("  %s не найден" % label)
    out("  'нахлёст' = насколько блок заходит на соседа за пивотом.")

    # ---- контур
    actor, spline = find_spline()
    if spline is None:
        out("")
        out("Контур не измерен - см. сообщение выше.")
        flush()
        return

    n = spline.get_number_of_spline_points()
    closed = spline.is_closed_loop()
    pts = [spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
           for i in range(n)]

    ptypes = []
    for i in range(n):
        try:
            raw = str(spline.get_spline_point_type(i))
            raw = raw.split(".")[-1].split(":")[0].strip().strip(">").strip()
            ptypes.append(raw.upper())
        except Exception:
            ptypes.append("?")
    curved = [t for t in ptypes if t not in ("LINEAR", "?")]

    out("")
    out("--- КОНТУР ----------------------------------------------------------")
    out("  актор: %s     точек: %d     Closed Loop: %s"
        % (actor.get_actor_label(), n, "да" if closed else "НЕТ"))
    if curved:
        out("  !! Есть точки не в режиме Linear: %s" % ", ".join(sorted(set(curved))))
        out("     Длины сторон считаются по прямой между точками - для кривых")
        out("     сегментов это НЕ длина дуги. Переведи точки в Linear.")
    if not closed:
        out("  !! Closed Loop выключен - замыкающая сторона не считается.")

    zs = [p.z for p in pts]
    if max(zs) - min(zs) > 1.0:
        out("  !! Точки на разной высоте: Z от %.1f до %.1f" % (min(zs), max(zs)))

    sa = shoelace_area(pts)
    area = abs(sa) / 10000.0
    n_sides = n if closed else n - 1
    per = 0.0
    for i in range(n_sides):
        per += dist_xy(pts[i], pts[(i + 1) % n])

    out("  периметр: %.1f см (%.2f м)     площадь: %.2f м2" % (per, per / 100.0, area))
    out("  обход: %s" % ("против часовой (CCW)" if sa > 0 else "по часовой (CW)"))

    out("")
    out("--- СТОРОНЫ ---------------------------------------------------------")
    role_w = {"wall": w_wall or 0.0, "cap_L": w_capl, "cap_R": w_capr,
              "corner_A": w_corna, "corner_B": w_cornb}
    ent = first("entrance")
    role_w["entrance"] = width_of(ent) if ent else 0.0

    def fixed_for(side_no):
        spec = SIDE_FIXED.get(side_no, SIDE_FIXED.get("rest", []))
        total = 0.0
        missing = []
        for r in spec:
            w = role_w.get(r, 0.0)
            if not w:
                missing.append(r)
            total += w
        return total, spec, missing

    hdr = "  %3s %12s %14s" % ("#", "длина, см", "Bend Angle")
    if w_wall:
        hdr += " %9s %10s %12s" % ("занято", "стен", "остаток, см")
    out(hdr)
    out("  " + "-" * 72)

    for i in range(n_sides):
        a = pts[i]
        b = pts[(i + 1) % n]
        L = dist_xy(a, b)
        if closed or (i + 2) <= (n - 1):
            c = pts[(i + 2) % n]
            tstr = "%+.2f" % turn_deg(a, b, c)
        else:
            tstr = "-"
        row = "  %3d %12.1f %14s" % (i + 1, L, tstr)
        if w_wall:
            fixed, _, _ = fixed_for(i + 1)
            usable = L - fixed
            cnt = int(math.floor(usable / w_wall)) if usable > 0 else 0
            rest = usable - cnt * w_wall
            row += " %9.1f %10d %12.1f" % (fixed, cnt, rest)
        out(row)

    if w_wall:
        out("")
        out("  Состав стороны, из которого посчитано 'занято':")
        for key in (1, "rest"):
            f, spec, missing = fixed_for(key if key == 1 else 2)
            label = "сторона 1  " if key == 1 else "стороны 2+ "
            out("    %s %-44s = %8.1f" % (label, " + ".join(spec), f))
            if missing:
                out("      !! нет блоков для ролей: %s" % ", ".join(missing))
        out("  стен = (длина - занято) / %.1f ; остаток - недобор до угла." % w_wall)
        out("  ЭТО ПРЕДПОЛОЖЕНИЕ по описанию Alex'а - подтвердить по слотам blksrc.")

    out("")
    out("--- ТОЧКИ (мировые) -------------------------------------------------")
    for i, p in enumerate(pts):
        out("  %3d  X %11.1f   Y %11.1f   Z %10.1f   [%s]"
            % (i, p.x, p.y, p.z, ptypes[i]))

    out("")
    out("Знак Bend Angle: '-' = поворот вправо (по часовой), '+' = влево.")
    out("Если знаки не те, что нужны генератору - контур нарисован в обратную")
    out("сторону: разверни порядок точек или инвертируй знак.")
    out("=" * 78)
    flush()


main()
