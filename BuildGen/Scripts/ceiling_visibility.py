# -*- coding: utf-8 -*-
# Adds a "Show Ceiling" switch to BuildGen.
#
# The ceiling has to disappear from the Unreal viewport while columns, stairs
# and the elevator are placed - otherwise it covers them. A Houdini display
# flag cannot do this: Houdini Engine takes the node OUTPUT, not the viewport
# picture. So the cut is a real one, made in the output.
#
# It sits AFTER stk_stack (the storey stacking), i.e. below every freeze seam:
#   * flipping it never wakes the frozen storey,
#   * and the freeze never swallows the switch itself.
# It removes prims named ceiling* , which covers the ground floor ('ceiling'),
# the copies ('ceiling_f1', 'ceiling_f2', ...) and the roof ('ceiling_roof').
#
# Contents.gz changes here, so the actor needs one Rebuild - which is why this
# is done while the actor is still empty and Rebuild is harmless.
import hou

R = []
def say(s): R.append(str(s))

TYPE = 'buildgen'
t  = hou.nodeType(hou.sopNodeTypeCategory(), TYPE)
dd = t.definition()
HDA = dd.libraryFilePath()
say('type file = %s' % HDA)

secs = dd.sections()
create_script = secs['CreateScript'].contents()
pymod         = secs['PythonModule'].contents()
say('before: CreateScript=%d b PythonModule=%d b' % (len(create_script), len(pymod)))

for nm in ('/obj/CEIL_TMP', '/obj/CEIL_CHECK'):
    o = hou.node(nm)
    if o:
        o.destroy()

tmp  = hou.node('/obj').createNode('geo', 'CEIL_TMP')
inst = tmp.createNode(TYPE, 'ceil_clean')
inst.allowEditingOfContents()
say('clean instance: %d nodes' % len(inst.allSubChildren()))

stk = inst.node('stk_stack')
ism = inst.node('ism_pack')
if not (stk and ism):
    raise hou.Error('stk_stack / ism_pack missing')
say('ism_pack currently fed by: %s' % (ism.inputs()[0].name() if ism.inputs() and ism.inputs()[0] else None))

def mk(name, ntype):
    n = inst.node(name)
    if n:
        n.destroy()
    return inst.createNode(ntype, name)

cut = mk('ceil_ue_cut', 'blast')
cut.setInput(0, stk)
cut.parm('group').set('@name=ceiling*')
# pick the Primitives entry of grouptype by label, no guessing at menu indices
gt = cut.parm('grouptype')
labels = gt.parmTemplate().menuLabels()
items  = gt.parmTemplate().menuItems()
pick = None
for i, lab in enumerate(labels):
    if lab.lower().startswith('prim'):
        pick = i
        break
if pick is None:
    say('  ! no Primitives entry in grouptype menu %s - left at default' % (labels,))
else:
    gt.set(pick)
    say('  grouptype = %r (%r)' % (items[pick], labels[pick]))
say('  blast group = %r  negate = %r' % (cut.parm('group').eval(), cut.parm('negate').eval()))

gate = mk('ceil_ue_gate', 'switch')
gate.setInput(0, stk)   # showceil = 1  -> untouched
gate.setInput(1, cut)   # showceil = 0  -> ceiling cut out
gate.parm('input').setExpression('1 - ch("../showceil")')
ism.setInput(0, gate)

sp = stk.position()
cut.setPosition((sp[0] + 1.6, sp[1] - 1.0))
gate.setPosition((sp[0], sp[1] - 2.0))
for n in (cut, gate):
    n.setColor(hou.Color((0.95, 0.75, 0.30)))
say('wired: ism_pack <- ceil_ue_gate (0=stk_stack, 1=ceil_ue_cut)')

# ------------------------------------------------------------------- parm ---
ptg = inst.parmTemplateGroup()
old = ptg.find('showceil')
if old:
    ptg.remove(old)
tg = hou.ToggleParmTemplate('showceil', 'Show Ceiling', default_value=True)
tg.setHelp('Uncheck to drop the ceiling from the Unreal output while placing '
           'columns, stairs and the elevator. View only - nothing is recomputed '
           'and no freeze is disturbed.')
anchor = ptg.find('frz_floorceil_folder')
if anchor:
    ptg.insertBefore(anchor, tg)
    say('parm showceil inserted before frz_floorceil_folder')
else:
    a2 = ptg.find('ceildown_uvangle')
    if a2:
        ptg.insertAfter(a2, tg)
        say('parm showceil inserted after ceildown_uvangle')
    else:
        ptg.appendToFolder(ptg.find('tab_floors7'), tg)
        say('parm showceil appended to Floors / Blocks')
inst.setParmTemplateGroup(ptg)

# ------------------------------------------------------------------- save ---
dd.updateFromNode(inst)
dd.addSection('CreateScript', create_script)
dd.addSection('PythonModule', pymod)
# the parm interface must come from the definition, not from the instance
ptg2 = dd.parmTemplateGroup()
if ptg2.find('showceil') is None:
    p2 = dd.parmTemplateGroup()
    a = p2.find('frz_floorceil_folder')
    if a:
        p2.insertBefore(a, tg)
    else:
        p2.appendToFolder(p2.find('tab_floors7'), tg)
    dd.setParmTemplateGroup(p2)
    dd.addSection('CreateScript', create_script)
    dd.addSection('PythonModule', pymod)
    say('showceil written straight to the definition interface')
say('after: CreateScript=%d b PythonModule=%d b sections=%s'
    % (len(dd.sections()['CreateScript'].contents()),
       len(dd.sections()['PythonModule'].contents()),
       sorted(dd.sections().keys())))
tmp.destroy()

# ----------------------------------------------------------------- verify ---
tv = hou.node('/obj').createNode('geo', 'CEIL_CHECK')
v  = tv.createNode(TYPE, 'chk')
v.allowEditingOfContents()
kids = set(c.name() for c in v.allSubChildren())
say('VERIFY: %d nodes' % len(kids))
for nm in ('ceil_ue_cut', 'ceil_ue_gate', 'stk_stack', 'ism_pack', 'merge_parts',
           'ue_walls', 'floor_mat', 'ceiling_gate', 'col_gate', 'ss_mir_gate',
           'ucx_dep', 'ucx_blocks', 'ucx_parts', 'ucx_ceiling', 'ucx_cols', 'curve1'):
    say('   %-14s %s' % (nm, 'ok' if nm in kids else '*** MISSING ***'))
vi = v.node('ism_pack')
vg = v.node('ceil_ue_gate')
say('   ism_pack.input0  = %s' % (vi.inputs()[0].name() if vi.inputs() and vi.inputs()[0] else None))
say('   gate inputs      = %s' % [i.name() if i else None for i in vg.inputs()])
say('   gate input expr  = %r  eval=%r' % (vg.parm('input').rawValue(), vg.parm('input').eval()))
say('   cut group        = %r' % v.node('ceil_ue_cut').parm('group').eval())
say('   showceil         = %r (default should be 1)' % v.evalParm('showceil'))
say('   freeze parms     = %s'
    % [k for k in ('blocks', 'floorceil', 'columns', 'stairs', 'storey')
       if v.parm('frz_%s_freeze' % k)])
m = v.hdaModule()
say('   phm freeze_stage = %s' % hasattr(m, 'freeze_stage'))
for pn in ('floors', 'blocksdir', 'closedist', 'floorinset', 'ceilthick'):
    if v.parm(pn):
        say('   default %-10s = %r' % (pn, v.evalParm(pn)))
try:
    v.node('output0').cook(force=True)
    say('   verify cook: ok, errors=%r' % (v.errors(),))
except Exception as e:
    say('   verify cook FAILED: %s' % e)
tv.destroy()
RESULT = '\n'.join(R)
