# cook_watch.py — наблюдатель за куками генератора (Houdini, главный поток)
#
# Пишет в <папка сцены>\Scripts\logs\cookcount_runNN.csv:
#   - строку каждый раз, когда у ноды вырос cookCount (значит она куканулась);
#   - строку "BLOCKED", если цикл простоя интерфейса стоял дольше 2 с
#     (то есть Houdini всё это время что-то считал и UI не отпускал).
# Время — UTC, стыкуется с BG.log.
#
# Запуск:  import cook_watch; cook_watch.start(11)
# Стоп:    cook_watch.stop()
# Профиль: cook_watch.profile_start(11) / cook_watch.profile_stop()

import hou
import os
import time

BASE = '/obj/buildgen/buildgen1'
NODES = ['', 'blk_rest', 'assemble', 'blk_markers', 'blk_library']  # '' = сам HDA
LOGDIR = hou.text.expandString('$HIP/Scripts/logs')
POLL = 0.25      # как часто опрашивать счётчики, с
BLOCKED = 2.0    # с какой паузы в UI считать, что движок был занят


def _stamp(t):
    return time.strftime('%Y.%m.%d-%H.%M.%S', time.gmtime(t)) + (':%03d' % int((t % 1) * 1000))


def stop():
    """Снять наблюдателя (если стоял)."""
    cb = getattr(hou.session, 'cook_watch_cb', None)
    if cb is not None:
        try:
            hou.ui.removeEventLoopCallback(cb)
        except Exception:
            pass
        hou.session.cook_watch_cb = None
    # Сторож ставил Manual. Вернуть авто-обновление, иначе сцена сохранится
    # в Manual и следующий запуск Houdini откроется с пустым вьюпортом.
    try:
        if hou.updateModeSetting() != hou.updateMode.AutoUpdate:
            hou.setUpdateMode(hou.updateMode.AutoUpdate)
    except Exception:
        pass
    return 'cook_watch: stopped (update mode -> Auto Update)'


FORCE_MANUAL = True   # ставить ли update mode Manual (можно снять на лету)
GUARD_OBJ = '/obj/buildgen'   # объект, который не должен рисоваться
GUARD_HOME = '/obj'           # куда выталкивать тянущие панели


def _guard():
    """Убрать всех, кто тянет геометрию генератора. Только флаги и навигация,
    ни одного кука не заказывает. Возвращает список сделанного."""
    acts = []

    # ⛔ НЕ трогать display-флаг объекта! Плагин читает его как HAPI isVisible и
    # ВЫБРАСЫВАЕТ невидимые части (HoudiniOutputTranslator.cpp:2150) — меши в UE
    # тогда не создаются вообще. Проверено прогоном 14.
    # Правильная ручка — режим обновления Houdini: в Manual вьюпорт не заказывает
    # пересчёт ради картинки, а состояние сцены не меняется.
    if FORCE_MANUAL:
        try:
            if hou.updateModeSetting() != hou.updateMode.Manual:
                hou.setUpdateMode(hou.updateMode.Manual)
                acts.append('update-mode:Manual')
        except Exception:
            pass

    obj = hou.node(GUARD_OBJ)
    if obj is not None:
        td, dp = obj.parm('tdisplay'), obj.parm('display')
        if td is not None and dp is not None and (td.eval() != 0 or dp.eval() != 1):
            try:
                td.set(0)
                dp.set(1)
                acts.append('display-RESTORED:%s' % GUARD_OBJ)
            except Exception:
                pass

    home = hou.node(GUARD_HOME)
    pullers = (hou.paneTabType.SceneViewer, hou.paneTabType.DetailsView)
    for t in hou.ui.paneTabs():
        try:
            if t.type() not in pullers:
                continue
            try:
                cur = t.pwd().path()
            except Exception:
                continue
            if not cur.startswith(GUARD_OBJ):
                continue
            try:
                if t.isPin():
                    t.setPin(False)
                    acts.append('unpin:%s' % t.type())
            except Exception:
                pass
            t.setPwd(home)
            acts.append('%s:%s->%s' % (str(t.type()).split('.')[-1], cur, GUARD_HOME))
        except Exception:
            pass

    return acts


def start(run=0, guard=True):
    """Поставить наблюдателя. run — номер прогона, идёт в имя файла.
    guard=True — заодно выталкивать вьюпорт и таблицу геометрии из генератора."""
    stop()
    path = os.path.join(LOGDIR, 'cookcount_run%s.csv' % run)
    if not os.path.exists(LOGDIR):
        os.makedirs(LOGDIR)
    with open(path, 'w') as f:
        f.write('utc,elapsed_s,event,node,cookcount,gap_s\n')

    st = {'prev': time.time(), 'poll': 0.0, 't0': time.time(), 'last': {}}

    def _write(rows):
        with open(path, 'a') as f:
            for r in rows:
                f.write(r)

    def tick():
        try:
            now = time.time()
            gap = now - st['prev']
            st['prev'] = now
            rows = []
            if gap > BLOCKED:
                rows.append('%s,%.3f,BLOCKED,,,%.3f\n' % (_stamp(now), now - st['t0'], gap))
            if now - st['poll'] >= POLL:
                st['poll'] = now
                if guard:
                    for a in _guard():
                        rows.append('%s,%.3f,GUARD,%s,,%.3f\n'
                                    % (_stamp(now), now - st['t0'], a, gap))
                for n in NODES:
                    node = hou.node(BASE + ('/' + n if n else ''))
                    if node is None:
                        continue
                    try:
                        c = node.cookCount()
                    except Exception:
                        continue
                    name = n if n else 'buildgen1'
                    if st['last'].get(name) != c:
                        st['last'][name] = c
                        rows.append('%s,%.3f,COOK,%s,%d,%.3f\n'
                                    % (_stamp(now), now - st['t0'], name, c, gap))
            if rows:
                _write(rows)
        except Exception:
            # наблюдатель не имеет права уронить интерфейс
            pass

    hou.session.cook_watch_cb = tick
    hou.ui.addEventLoopCallback(tick)
    return 'cook_watch: started -> %s' % path


def profile_start(run=0):
    """Performance Monitor. Ссылку держим в hou.session, иначе профиль умирает."""
    p = hou.perfMon.startProfile('run%s' % run)
    hou.session.perf_profile = p
    return 'profile: started, active=%s' % p.isActive()


def profile_stop(run=0):
    p = getattr(hou.session, 'perf_profile', None)
    if p is None:
        return 'profile: no reference in hou.session'
    p.stop()
    hperf = os.path.join(LOGDIR, 'perf_run%s.hperf' % run)
    csv = os.path.join(LOGDIR, 'perf_run%s.csv' % run)
    p.save(hperf)
    try:
        p.exportAsCSV(csv)
    except Exception:
        csv = '(csv export failed)'
    hou.session.perf_profile = None
    return 'profile: saved %s | %s' % (hperf, csv)
