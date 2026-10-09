# -*- coding: utf-8 -*-
# Two clean-ups written into the BuildGen type, done while nothing is assigned.
#
# 1. Remove the leftovers of the first (disk-cache) freeze attempt:
#    frz_walls_sw / frz_floor_sw / frz_walls_read / frz_floor_read.
#    Their switch expressions still reference the 'frozen' toggle, which was
#    deleted - every fresh actor reports "Bad parameter reference: ../frozen".
#    The staged freeze works by hard-locking nodes, so these are dead weight.
#
# 2. ceiling_lift.ty: keep reading the wall height exactly as before, but when
#    it is missing fall back to the real storey height (ue_walls) instead of the
#    hard-coded 4. Alex confirmed the storey pitch works today, so the primary
#    branch is left untouched on purpose - only the fallback changes.
#
# stk_stack is deliberately NOT touched: Alex measured "+floor" landing exactly
# on 12.5, so its height source is correct.
import hou

R = []
def say(s): R.append(str(s))

TYPE = 'buildgen'
dd = hou.nodeType(hou.sopNodeTypeCategory(), TYPE).definition()
say('type file = %s' % dd.libraryFilePath())
secs = dd.sections()
create_script = secs['CreateScript'].contents()
pymod         = secs['PythonModule'].contents()
say('before: CreateScript=%d b PythonModule=%d b' % (len(create_script), len(pymod)))

for nm in ('/obj/CLEAN_TMP', '/obj/CLEAN_CHECK'):
    o = hou.node(nm)
    if o:
        o.destroy()

tmp  = hou.node('/obj').createNode('geo', 'CLEAN_TMP')
inst = tmp.createNode(TYPE, 'clean')
inst.allowEditingOfContents()
say('clean instance: %d nodes' % len(inst.allSubChildren()))

# --- 1. rewire around the dead freeze switches, then delete them -------------
walls = inst.node('walls')
stk   = inst.node('stk_stack')
ws    = inst.node('walls_strip')
mp    = inst.node('merge_parts')
say('before: walls.input0=%s  stk_stack.input0=%s'
    % (walls.inputs()[0].name() if walls.inputs() and walls.inputs()[0] else None,
       stk.inputs()[0].name() if stk.inputs() and stk.inputs()[0] else None))
walls.setInput(0, ws)
stk.setInput(0, mp)
killed = []
for nm in ('frz_walls_sw', 'frz_floor_sw', 'frz_walls_read', 'frz_floor_read'):
    nd = inst.node(nm)
    if nd:
        nd.destroy()
        killed.append(nm)
say('deleted: %s' % killed)
say('after : walls.input0=%s  stk_stack.input0=%s'
    % (walls.inputs()[0].name() if walls.inputs() and walls.inputs()[0] else None,
       stk.inputs()[0].name() if stk.inputs() and stk.inputs()[0] else None))

# --- 2. ceiling lift: same primary source, real fallback ---------------------
cl = inst.node('ceiling_lift')
old_ty = cl.parm('ty').rawValue()
new_ty = ('if(bbox("../walls", D_YSIZE) > 0.001, bbox("../walls", D_YSIZE), '
          'bbox("../ue_walls", D_YSIZE))')
cl.parm('ty').setExpression(new_ty)
say('ceiling_lift.ty')
say('   was : %s' % old_ty)
say('   now : %s' % cl.parm('ty').rawValue())

# stk_stack must stay as it is
sk = inst.node('stk_stack')
say("stk_stack untouched: contains \"par.node('walls')\" = %s"
    % ("par.node('walls')" in sk.parm('python').eval()))

# --- save --------------------------------------------------------------------
dd.updateFromNode(inst)
dd.addSection('CreateScript', create_script)
dd.addSection('PythonModule', pymod)
say('after: CreateScript=%d b PythonModule=%d b sections=%s'
    % (len(dd.sections()['CreateScript'].contents()),
       len(dd.sections()['PythonModule'].contents()),
       sorted(dd.sections().keys())))
tmp.destroy()

# --- verify on a fresh instance ---------------------------------------------
tv = hou.node('/obj').createNode('geo', 'CLEAN_CHECK')
v  = tv.createNode(TYPE, 'chk')
v.allowEditingOfContents()
kids = set(c.name() for c in v.allSubChildren())
say('VERIFY: %d nodes' % len(kids))
for nm in ('frz_walls_sw', 'frz_floor_sw', 'frz_walls_read', 'frz_floor_read'):
    say('   %-16s %s' % (nm, 'GONE ok' if nm not in kids else '*** STILL THERE ***'))
for nm in ('ceil_ue_cut', 'ceil_ue_gate', 'ue_walls', 'walls', 'merge_parts', 'stk_stack',
           'ucx_dep', 'ucx_blocks', 'ucx_parts', 'ucx_ceiling', 'ucx_cols', 'curve1', 'ism_pack'):
    say('   %-16s %s' % (nm, 'ok' if nm in kids else '*** MISSING ***'))
vw, vs = v.node('walls'), v.node('stk_stack')
say('   walls.input0     = %s' % (vw.inputs()[0].name() if vw.inputs() and vw.inputs()[0] else None))
say('   stk_stack.input0 = %s' % (vs.inputs()[0].name() if vs.inputs() and vs.inputs()[0] else None))
say('   ism_pack.input0  = %s' % (v.node('ism_pack').inputs()[0].name()))
say('   ceiling_lift.ty  = %r' % v.node('ceiling_lift').parm('ty').rawValue())
say('   showceil=%r' % v.evalParm('showceil'))
say('   freeze pairs = %s'
    % [k for k in ('blocks', 'floorceil', 'columns', 'stairs', 'storey')
       if v.parm('frz_%s_freeze' % k)])
say('   frozen parm gone = %s' % (v.parm('frozen') is None))
bad = []
for c in v.allSubChildren():
    for p in c.parms():
        try:
            rv = p.rawValue()
        except Exception:
            continue
        if isinstance(rv, str) and '../frozen' in rv:
            bad.append('%s/%s' % (c.name(), p.name()))
say('   refs to ../frozen left: %s' % (bad if bad else 'none'))
try:
    v.node('output0').cook(force=True)
    say('   verify cook: ok, errors=%r' % (v.errors(),))
except Exception as e:
    say('   verify cook FAILED: %s' % e)
tv.destroy()
RESULT = '\n'.join(R)
