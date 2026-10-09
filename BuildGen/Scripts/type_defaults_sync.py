# -*- coding: utf-8 -*-
"""
12-09-2026. Один хозяин у чисел типа buildgen.

1) Переносит рабочие числа из снимка CreateScript в настоящие дефолты (DialogScript).
2) Вырезает из CreateScript большую строку opparm — снимок значений, который
   штамповался поверх дефолтов на каждый новый актор.
   Остаются только счётчики мультипармов (floors / roofsides / sides1 / blocks*).

После этого дефолты правятся ТОЛЬКО в интерфейсе типа, и ритуал
"вернуть CreateScript" после updateFromNode больше не нужен.

Запуск: внутри Houdini, при отсутствии актора генератора в сцене.
"""
import hou

# парм -> новый дефолт (значения взяты из снимка: ими и жили все прогоны)
PROMOTE = {
    # 12-09, после прогона 21 — числа названы Alex'ом
    'floorinset':  0.3,    # панель: Floor Offset        (было 0.616)
    'ceiloffset': -0.3,    # панель: Offset inside/outside (было 0.0)
    'ceilthick':   0.1,    # толщина потолка          (было 0.18)
}

def run():
    d = hou.sopNodeTypeCategory().nodeTypes()['buildgen'].definition()
    report = {'defaults': [], 'createscript': None}

    # --- 1. дефолты в DialogScript ---
    ptg = d.parmTemplateGroup()
    for name, val in PROMOTE.items():
        pt = ptg.find(name)
        if pt is None:
            report['defaults'].append((name, 'НЕТ В ИНТЕРФЕЙСЕ'))
            continue
        old = pt.defaultValue()
        pt.setDefaultValue((val,) if isinstance(old, (tuple, list)) else val)
        ptg.replace(name, pt)
        report['defaults'].append((name, old, val))
    d.setParmTemplateGroup(ptg)

    # --- 2. чистка CreateScript ---
    cs = d.sections()['CreateScript'].contents()
    keep = [l for l in cs.splitlines() if not l.startswith('opparm $arg1 save_from_ue')]
    new = '\n'.join(keep) + '\n'
    d.addSection('CreateScript', new)
    report['createscript'] = (len(cs), len(new))
    return report
