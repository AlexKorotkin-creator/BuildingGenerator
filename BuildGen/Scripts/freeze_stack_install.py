# -*- coding: utf-8 -*-
"""
12-09-2026. Шестая пара замков: FREEZE STACK / UNFREEZE STACK.

Зачем. Все этажи лепит ОДНА нода stk_stack из одного «оригинала» — собранного
первого этажа. Каждый «+этаж» гонит её по всему списку сверху донизу: копирует
этаж, двигает по высоте, заново пересобирает лестницы под высоту, чинит
развёртку шахт. Нижние этажи проходят через это каждый раз.

Замок «в лоб» на stk_stack не годится: застынет весь стек, и «+этаж» перестанет
работать. Поэтому нода разрезается надвое одним и тем же кодом:

    stk_below  (stk_part = 'below')  — этажи 0 .. frozen-1   <- на неё вешается замок
    stk_stack  (stk_part = 'top')    — этажи frozen .. конец
    stk_merge                        — их слияние, дальше по цепочке как раньше

Сколько этажей заморожено, хранит парм `stk_frozen` на самом HDA.
Кнопка FREEZE STACK: посчитать этажи -> записать в stk_frozen -> прокукать
stk_below -> повесить hard lock. UNFREEZE STACK: снять замок, stk_frozen = 0.

Запуск: внутри Houdini, при ОТСУТСТВИИ актора генератора в сцене.
    exec(open(hou.text.expandString('$HIP/Scripts/freeze_stack_install.py')).read())
    run()
"""

import hou
import shutil

LIB = hou.text.expandString('$HIP/hda/BuildGen.hda')
BAK = hou.text.expandString('$HIP/hda/BuildGen_bak_before_freezestack.hda')


# --------------------------------------------------------------- патч кода SOP

MARK_TOTAL = "total = len(contribs)"

INS_TOTAL = """total = len(contribs)

# --- FREEZE STACK: какую часть стопки считает ЭТА нода ----------------------
# 'below' - только замороженные этажи (её и морозят), 'top' - только новые.
# Пропущенные витки цикла всё равно прокручиваются: yoff и prev_h должны
# накопиться, иначе верхние этажи встанут не на своей высоте.
frozen = int(ev('stk_frozen', 0))
if frozen < 0:
    frozen = 0
if frozen > total:
    frozen = total
_ppart = node.parm('stk_part')
_part = _ppart.evalAsString() if _ppart is not None else 'top'
if _part == 'below':
    k_lo, k_hi = 0, frozen
else:
    k_lo, k_hi = frozen, total"""

MARK_PREVH = "    prev_h = storey_h(srcf)\n"

INS_PREVH = """    prev_h = storey_h(srcf)
    if k < k_lo or k >= k_hi:
        continue
"""

MARK_GROUND = "\ngeo.merge(ground)"

INS_GROUND = """
# ground-only части (плита пола, кабина лифта) принадлежат этажу 0 - их отдаёт
# та половина, которая этот этаж и считает
if k_hi > k_lo and k_lo == 0:
    geo.merge(ground)"""


def patch_code(code):
    assert code.count(MARK_TOTAL) == 1, 'маркер total не найден'
    assert code.count(MARK_PREVH) == 1, 'маркер prev_h не найден'
    assert code.count(MARK_GROUND) == 1, 'маркер geo.merge(ground) не найден'
    code = code.replace(MARK_TOTAL, INS_TOTAL, 1)
    code = code.replace(MARK_PREVH, INS_PREVH, 1)
    code = code.replace(MARK_GROUND, INS_GROUND, 1)
    return code


# ------------------------------------------------------- патч PythonModule

PM_OLD_STAGES = """    ('storey',    ('merge_parts',)),
)"""

PM_NEW_STAGES = """    ('storey',    ('merge_parts',)),
    ('stack',     ('stk_below',)),
)"""

PM_OLD_UNFRZ = """    for k, _n in FRZ_STAGES[i:]:
        for n in _frz_nodes(node, k):
            n.setHardLocked(False)
        _frz_say(node, k, 'live')"""

PM_NEW_UNFRZ = """    for k, _n in FRZ_STAGES[i:]:
        for n in _frz_nodes(node, k):
            n.setHardLocked(False)
        if k == 'stack':
            _p = node.parm('stk_frozen')
            if _p is not None:
                _p.set(0)
        _frz_say(node, k, 'live')"""

PM_FUNCS = '''

# --- FREEZE STACK ----------------------------------------------------------
# Сколько этажей сейчас в здании: каждый FLOOR даёт 1 или столько, сколько
# стоит в Make Copy / Copies; крыша добавляет ещё один сверху.

def _stk_total(node):
    try:
        n = int(node.evalParm('floors') or 1)
    except Exception:
        n = 1
    if n < 1:
        n = 1
    tot = 0
    for i in range(1, n + 1):
        c = 1
        try:
            if int(node.evalParm('floorcopy%d' % i)):
                c = max(1, int(node.evalParm('floorcopies%d' % i)))
        except Exception:
            c = 1
        tot += c
    try:
        if int(node.evalParm('makeroof')):
            tot += 1
    except Exception:
        pass
    return tot


def freeze_stack(kwargs):
    node = kwargs['node']
    nb = node.node('stk_below')
    if nb is None:
        _frz_say(node, 'stack', 'ERROR - stk_below not found')
        return
    if nb.isHardLocked():
        _frz_say(node, 'stack', 'already frozen')
        return
    p = node.parm('stk_frozen')
    if p is None:
        _frz_say(node, 'stack', 'ERROR - stk_frozen parm missing')
        return
    tot = _stk_total(node)
    if tot < 1:
        _frz_say(node, 'stack', 'nothing to freeze')
        return
    p.set(tot)
    try:
        nb.cook(force=True)
        g = nb.geometry()
    except Exception as e:
        p.set(0)
        _frz_say(node, 'stack', 'ERROR - %s' % e)
        return
    if g is None or not len(g.prims()):
        p.set(0)
        _frz_say(node, 'stack', 'nothing to freeze - build the storeys first')
        return
    nb.setHardLocked(True)
    _frz_say(node, 'stack', 'FROZEN - %d storeys, %d prims' % (tot, len(g.prims())))


def unfreeze_stack(kwargs):
    node = kwargs['node']
    nb = node.node('stk_below')
    if nb is not None:
        nb.setHardLocked(False)
    p = node.parm('stk_frozen')
    if p is not None:
        p.set(0)
    _frz_say(node, 'stack', 'live')
'''


def patch_pm(pm):
    assert pm.count(PM_OLD_STAGES) == 1, 'FRZ_STAGES не найден'
    assert pm.count(PM_OLD_UNFRZ) == 1, 'unfreeze_stage не найден'
    assert 'def freeze_stack' not in pm, 'freeze_stack уже стоит'
    pm = pm.replace(PM_OLD_STAGES, PM_NEW_STAGES, 1)
    pm = pm.replace(PM_OLD_UNFRZ, PM_NEW_UNFRZ, 1)
    return pm + PM_FUNCS


# ------------------------------------------------------------------- интерфейс

def build_interface(d):
    ptg = d.parmTemplateGroup()
    added = []

    if ptg.find('stk_frozen') is None:
        pt = hou.IntParmTemplate('stk_frozen', 'Frozen Storeys', 1,
                                 default_value=(0,), min=0, max=100)
        pt.hide(True)
        ptg.append(pt)
        added.append('stk_frozen')

    if ptg.find('frz_stack_freeze') is None:
        f = hou.FolderParmTemplate('frz_stack_folder', 'Freeze  \u2014  Storey Stack',
                                   folder_type=hou.folderType.Collapsible)
        b1 = hou.ButtonParmTemplate('frz_stack_freeze', 'FREEZE STACK')
        b1.setScriptCallback('hou.phm().freeze_stack(kwargs)')
        b1.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        b2 = hou.ButtonParmTemplate('frz_stack_unfreeze', 'UNFREEZE STACK')
        b2.setScriptCallback('hou.phm().unfreeze_stack(kwargs)')
        b2.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        st = hou.StringParmTemplate('frz_stack_status', 'Status', 1,
                                    default_value=('live',))
        f.addParmTemplate(b1)
        f.addParmTemplate(b2)
        f.addParmTemplate(st)

        sibling = ptg.find('frz_storey_folder')
        if sibling is not None:
            ptg.insertAfter(sibling, f)
        else:
            ptg.append(f)
        added.append('frz_stack_folder')

    d.setParmTemplateGroup(ptg)
    return added


# ------------------------------------------------------------------------ run

def run():
    rep = {}
    nt = hou.sopNodeTypeCategory().nodeTypes()['buildgen']
    d = nt.definition()

    live = [n.path() for n in hou.node('/obj').allSubChildren()
            if n.type().name() == 'buildgen']
    assert not live, u'в сцене есть акторы генератора: %s' % live

    shutil.copy2(d.libraryFilePath(), BAK)
    rep['бэкап'] = BAK

    # ---------- 1. содержимое: через ЧИСТЫЙ инстанс ----------
    tmp = hou.node('/obj').createNode('geo', 'tmp_freezestack')
    try:
        inst = tmp.createNode('buildgen')
        inst.allowEditingOfContents()
        before = sorted(n.name() for n in inst.children())

        stk = inst.node('stk_stack')
        assert stk is not None, 'ноды stk_stack нет'
        assert inst.node('stk_below') is None, 'stk_below уже есть'

        outs = list(stk.outputConnections())
        ins = [(c.inputIndex(), c.inputNode(), c.outputIndex())
               for c in stk.inputConnections()]

        below = hou.copyNodesTo([stk], inst)[0]
        below.setName('stk_below', unique_name=True)
        for idx, src, oidx in ins:
            below.setInput(idx, src, oidx)
        below.setPosition(stk.position() + hou.Vector2(0.0, -1.4))

        def part_parm(n, val):
            g = n.parmTemplateGroup()
            if g.find('stk_part') is None:
                g.append(hou.StringParmTemplate('stk_part', 'Stack Part', 1,
                                                default_value=('top',)))
                n.setParmTemplateGroup(g)
            n.parm('stk_part').set(val)

        part_parm(stk, 'top')
        part_parm(below, 'below')

        code = patch_code(stk.parm('python').eval())
        stk.parm('python').set(code)
        below.parm('python').set(code)

        mrg = inst.createNode('merge', 'stk_merge')
        mrg.setPosition(stk.position() + hou.Vector2(1.6, -0.7))
        mrg.setInput(0, below)
        mrg.setInput(1, stk)
        for c in outs:
            c.outputNode().setInput(c.inputIndex(), mrg, 0)

        rep['перепаяно_потребителей'] = [c.outputNode().name() for c in outs]

        d.updateFromNode(inst)
        after = sorted(n.name() for n in inst.children())
        rep['узлов_до'] = len(before)
        rep['узлов_после'] = len(after)
        rep['новые_узлы'] = [n for n in after if n not in before]
        rep['потерянные_узлы'] = [n for n in before if n not in after]
        assert not rep['потерянные_узлы'], u'ПОТЕРЯНЫ УЗЛЫ: %s' % rep['потерянные_узлы']
    finally:
        tmp.destroy()

    # ---------- 2. PythonModule ----------
    pm = d.sections()['PythonModule'].contents()
    d.addSection('PythonModule', patch_pm(pm))
    rep['PythonModule'] = (len(pm), len(d.sections()['PythonModule'].contents()))

    # ---------- 3. интерфейс ----------
    rep['интерфейс'] = build_interface(d)

    # ---------- 4. проверка на чистом инстансе ----------
    tmp2 = hou.node('/obj').createNode('geo', 'tmp_fs_check')
    try:
        n2 = tmp2.createNode('buildgen')
        rep['проверка'] = {
            'stk_below': n2.node('stk_below') is not None,
            'stk_merge': n2.node('stk_merge') is not None,
            'stk_frozen': n2.parm('stk_frozen').eval() if n2.parm('stk_frozen') else 'НЕТ',
            'кнопка_freeze': n2.parm('frz_stack_freeze') is not None,
            'кнопка_unfreeze': n2.parm('frz_stack_unfreeze') is not None,
            'phm_freeze_stack': hasattr(n2.hdaModule(), 'freeze_stack'),
            'phm_unfreeze_stack': hasattr(n2.hdaModule(), 'unfreeze_stack'),
            'stk_part_top': n2.node('stk_stack').parm('stk_part').evalAsString(),
            'stk_part_below': n2.node('stk_below').parm('stk_part').evalAsString(),
        }
    finally:
        tmp2.destroy()

    rep['CreateScript_len'] = len(d.sections()['CreateScript'].contents())
    return rep
