# -*- coding: utf-8 -*-
# Re-implements FREEZE as an in-place hard lock instead of a disk cache.
#
# Why: saving the storey to .bgeo.sc expands every packed block copy into full
# geometry - 4.0 GB for 'walls' plus 528 MB for 'merge_parts' on one storey.
# A hard lock keeps the cooked geometry inside the node: instant, zero bytes on
# disk, and nothing above the locked node ever cooks again.
#
# This touches ONLY the PythonModule section - the node network (Contents.gz) is
# untouched, so no Reimport and no Rebuild are needed and the built storey is
# not disturbed. The live instance resolves hou.phm() from the definition, so
# the new code takes effect on the next button press.
import hou

R = []
def say(s): R.append(str(s))

MARK = '# ---------------------------------------------------------------- FREEZE ----'

NEW = MARK + '''
# FREEZE = hard lock on the two nodes the finished storey hangs off:
#   'merge_parts' - the assembled storey that stk_stack multiplies upward
#   'walls'       - stk_stack ALSO pulls this one by name for the storey height,
#                   and it sits in the heavy block-layout branch
# Locked, both hold their cooked geometry and never ask upstream again, while
# stk_stack (+floor, overrides, stacking) keeps running off them.
# The 'frozen' toggle and the frz_* file/switch nodes are left over from the
# disk-cache attempt and are deliberately NOT used - see frzstatus for state.

FRZ_NODES = ('merge_parts', 'walls')

def _frz_targets(node):
    out = []
    for nm in FRZ_NODES:
        n = node.node(nm)
        if n is not None:
            out.append(n)
    return out

def freeze_floor(kwargs):
    node = kwargs['node']
    tg = _frz_targets(node)
    if not tg:
        node.parm('frzstatus').set('ERROR - merge_parts / walls not found')
        return
    if all(n.isHardLocked() for n in tg):
        node.parm('frzstatus').set('already frozen - press UNFREEZE first')
        return
    total = 0
    for n in tg:
        g = n.geometry()
        if g is None or not len(g.prims()):
            node.parm('frzstatus').set('nothing to freeze - %s is empty' % n.name())
            return
        total += len(g.prims())
    for n in tg:
        n.setHardLocked(True)
    node.parm('frzstatus').set('FROZEN - %d prims locked in %s'
                              % (total, ' + '.join(n.name() for n in tg)))

def unfreeze_floor(kwargs):
    node = kwargs['node']
    tg = _frz_targets(node)
    for n in tg:
        n.setHardLocked(False)
    node.parm('frzstatus').set('live')

def freeze_state(node):
    tg = _frz_targets(node)
    return bool(tg) and all(n.isHardLocked() for n in tg)
'''

t  = hou.nodeType(hou.sopNodeTypeCategory(), 'buildgen')
dd = t.definition()
secs = dd.sections()
pm = secs['PythonModule'].contents()
say('PythonModule before = %d b' % len(pm))

i = pm.find(MARK)
if i == -1:
    say('marker not found - appending fresh')
    newpm = pm.rstrip() + '\n\n\n' + NEW
else:
    say('marker found at %d - replacing the old disk-cache block' % i)
    newpm = pm[:i].rstrip() + '\n\n\n' + NEW

create_script = secs['CreateScript'].contents() if 'CreateScript' in secs else None
dd.addSection('PythonModule', newpm)
if create_script is not None and dd.sections()['CreateScript'].contents() != create_script:
    dd.addSection('CreateScript', create_script)
    say('CreateScript restored')
say('PythonModule after  = %d b' % len(dd.sections()['PythonModule'].contents()))
say('sections = %s' % sorted(dd.sections().keys()))
say('CreateScript = %d b' % len(dd.sections()['CreateScript'].contents()))

# the live instance must see the new functions without any rebuild
n = hou.node('/obj/buildgen/buildgen1')
if n:
    m = n.hdaModule()
    say('live proxy: freeze_floor=%s unfreeze_floor=%s freeze_state=%s'
        % (hasattr(m, 'freeze_floor'), hasattr(m, 'unfreeze_floor'), hasattr(m, 'freeze_state')))
    say('live proxy: merge_parts locked=%s  walls locked=%s'
        % (n.node('merge_parts').isHardLocked(), n.node('walls').isHardLocked()))
    say('live proxy: frozen=%r frzstatus=%r' % (n.evalParm('frozen'), n.evalParm('frzstatus')))
    say('live proxy: closeloop=%r makefloor=%r' % (n.evalParm('closeloop'), n.evalParm('makefloor')))
RESULT = '\n'.join(R)
