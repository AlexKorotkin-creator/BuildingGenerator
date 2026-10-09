# -*- coding: utf-8 -*-
"""
Per-floor "Freeze Floor" button for BuildGen.

Alex, 12-09-2026 (run 22): the sixth freeze pair landed as one global folder
`Freeze - Storey Stack` at the bottom of the Floors/Blocks tab. It has to be a
button INSIDE the FLOOR # multiparm, right under `Copies`, so it shows up on
every floor that gets added.

Two edits, both straight into the definition (no clean instance, no
updateFromNode - the contents of the type are not touched):
  DialogScript  -> button parm `frzfloor#` after `floorcopies#`
  PythonModule  -> freeze_floor(kwargs) + _stk_total_upto(node, upto)

Run with NO generator actor in the level: setParmTemplateGroup on a live
instance takes Houdini down with signal 11.
"""

import hou, shutil, datetime

LIB = hou.text.expandString('$HIP/hda/BuildGen.hda')
REPORT = []


def say(msg):
    REPORT.append(msg)
    print(msg)


# --------------------------------------------------------------- the new code
NEW_CODE = '''

# --- FREEZE FLOOR (per-floor button inside the FLOOR multiparm) -------------
# Alex, 12-09-2026: the lock has to be reachable on every floor, not once per
# building. `frzfloor<N>` freezes storeys 1..N inclusive (copies counted), so
# the flow is: +floor -> assign its blocks -> let it draw -> Make Copy +
# Copies -> Freeze Floor -> next +floor.

def _stk_total_upto(node, upto):
    """Storeys from the ground up to and including FLOOR <upto>, copies counted."""
    tot = 0
    for i in range(1, upto + 1):
        c = 1
        try:
            if int(node.evalParm('floorcopy%d' % i)):
                c = max(1, int(node.evalParm('floorcopies%d' % i)))
        except Exception:
            c = 1
        tot += c
    return tot


def _frz_floor_index(parm):
    """FLOOR number out of the button's own name: frzfloor3 -> 3."""
    digits = ''
    for ch in reversed(parm.name()):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    return int(digits) if digits else 0


def freeze_floor_upto(kwargs):
    node = kwargs['node']
    idx = _frz_floor_index(kwargs['parm'])
    if idx < 1:
        _frz_say(node, 'stack', 'ERROR - cannot read the floor number')
        return
    nb = node.node('stk_below')
    if nb is None:
        _frz_say(node, 'stack', 'ERROR - stk_below not found')
        return
    p = node.parm('stk_frozen')
    if p is None:
        _frz_say(node, 'stack', 'ERROR - stk_frozen parm missing')
        return
    tot = _stk_total_upto(node, idx)
    if tot < 1:
        _frz_say(node, 'stack', 'nothing to freeze')
        return
    was_locked = nb.isHardLocked()
    was_count = p.eval()
    if was_locked:
        # already frozen lower down - let it go, then re-freeze deeper
        nb.setHardLocked(False)
    p.set(tot)
    try:
        nb.cook(force=True)
        g = nb.geometry()
    except Exception as e:
        p.set(was_count)
        if was_locked:
            nb.setHardLocked(True)
        _frz_say(node, 'stack', 'ERROR - %s' % e)
        return
    if g is None or not len(g.prims()):
        p.set(was_count)
        if was_locked:
            nb.setHardLocked(True)
        _frz_say(node, 'stack', 'nothing to freeze - build the storeys first')
        return
    nb.setHardLocked(True)
    _frz_say(node, 'stack', 'FROZEN thru FLOOR %d - %d storeys, %d prims'
             % (idx, tot, len(g.prims())))
'''


def main():
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = LIB.replace('.hda', '') + '_bak_%s_before_freezefloor.hda' % stamp
    shutil.copy2(LIB, bak)
    say('backup -> %s' % bak)

    defs = hou.hda.definitionsInFile(LIB)
    if not defs:
        raise RuntimeError('no definitions in %s' % LIB)
    d = defs[-1]
    say('definition: %s  (%s)' % (d.nodeTypeName(), d.nodeTypeCategory().name()))

    # ---- 1. PythonModule (goes first: it cannot be clobbered by step 2) ----
    pm = d.sections()['PythonModule'].contents()
    if 'def freeze_floor_upto(' in pm:
        say('PythonModule: freeze_floor_upto already there, left alone')
    else:
        d.addSection('PythonModule', pm + NEW_CODE)
        say('PythonModule: %d -> %d bytes' % (len(pm), len(pm + NEW_CODE)))

    # ---- 2. DialogScript: the button inside the FLOOR multiparm ------------
    ptg = d.parmTemplateGroup()
    existing = ptg.find('frzfloor#')
    if existing is None:
        anchor = ptg.find('floorcopies#')
        if anchor is None:
            raise RuntimeError('floorcopies# not found - layout changed, stopping')
    if True:
        btn = hou.ButtonParmTemplate(
            'frzfloor#',
            'FLOOR #  \u2014  Freeze Floor',
            script_callback='hou.phm().freeze_floor_upto(kwargs)',
            script_callback_language=hou.scriptLanguage.Python,
            help=('Freeze this floor and every floor below it, copies included. '
                  'Press it only after the floor has drawn in Unreal: the lock '
                  'seals whatever the node holds right now.'),
        )
        if existing is None:
            ptg.insertAfter(anchor, btn)
            say('DialogScript: frzfloor# inserted after floorcopies#')
        else:
            ptg.replace('frzfloor#', btn)
            say('DialogScript: frzfloor# already present - callback rewritten')
        d.setParmTemplateGroup(ptg)

    # ---- 3. verify ---------------------------------------------------------
    d2 = hou.hda.definitionsInFile(LIB)[-1]
    ptg2 = d2.parmTemplateGroup()
    ok_parm = ptg2.find('frzfloor#') is not None
    ok_code = 'def freeze_floor_upto(' in d2.sections()['PythonModule'].contents()
    say('verify: frzfloor# in interface = %s, freeze_floor_upto() in PythonModule = %s'
        % (ok_parm, ok_code))
    if ok_parm:
        t = ptg2.find('frzfloor#')
        say('verify: label = %r, callback = %r' % (t.label(), t.scriptCallback()))
    # the five old pairs and the global stack pair must still be there
    for n in ('frz_blocks_freeze', 'frz_floorceil_freeze', 'frz_columns_freeze',
              'frz_stairs_freeze', 'frz_storey_freeze', 'frz_stack_freeze'):
        if ptg2.find(n) is None:
            say('LOST: %s' % n)
    hou.hda.reloadFile(LIB)
    say('reloaded %s' % LIB)
    return '\n'.join(REPORT)
