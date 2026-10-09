# -*- coding: utf-8 -*-
# Installs the two-seam FREEZE into the BuildGen HDA type.
# Safe route (memory: reference_sg2_buildgen_slab_curve_workflow):
#   clean instance -> edit -> updateFromNode -> restore CreateScript.
# NEVER written from the live proxy /obj/buildgen/buildgen1.
import hou, os

HDA_FILE  = hou.text.expandString('$HIP/hda/BuildGen.hda')
TYPE_NAME = 'buildgen'
R = []
def say(s): R.append(str(s))

PYMOD_ADD = '''

# ---------------------------------------------------------------- FREEZE ----
# Two seams keep a finished storey from being recomputed:
#   frz_walls_sw  in front of 'walls'         - stk_stack pulls walls by name
#   frz_floor_sw  merge_parts -> stk_stack    - the finished storey itself
# Both follow the single 'frozen' toggle. Frozen = nothing above either seam
# cooks, while stk_stack (+floor / overrides) keeps running off the cache.

def _frz_files(node):
    import os
    base = node.evalParm('frzpath')
    return (os.path.join(base, 'frz_walls.bgeo.sc'),
            os.path.join(base, 'frz_floor.bgeo.sc'))

def freeze_floor(kwargs):
    import os
    node = kwargs['node']
    if node.evalParm('frozen'):
        node.parm('frzstatus').set('already frozen - press UNFREEZE first')
        return
    wf, ff = _frz_files(node)
    d = os.path.dirname(ff)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    wg = node.node('walls').geometry()
    fg = node.node('merge_parts').geometry()
    if not len(fg.prims()):
        node.parm('frzstatus').set('nothing to freeze - the storey is empty')
        return
    wg.saveToFile(wf)
    fg.saveToFile(ff)
    node.parm('frozen').set(1)
    node.parm('frzstatus').set('FROZEN - %d prims cached in %s' % (len(fg.prims()), d))

def unfreeze_floor(kwargs):
    node = kwargs['node']
    node.parm('frozen').set(0)
    node.parm('frzstatus').set('live')
'''

# ---------------------------------------------------------------- build -----
for nm in ('/obj/FRZ_TMP', '/obj/FRZ_VERIFY'):
    old = hou.node(nm)
    if old:
        old.destroy()

tmp  = hou.node('/obj').createNode('geo', 'FRZ_TMP')
inst = tmp.createNode(TYPE_NAME, 'frz_clean')
inst.allowEditingOfContents()
say('clean instance: %d nodes' % len(inst.allSubChildren()))

walls = inst.node('walls')
mp    = inst.node('merge_parts')
stk   = inst.node('stk_stack')
if not (walls and mp and stk):
    raise hou.Error('missing walls / merge_parts / stk_stack in clean instance')
wsrc = walls.inputs()[0]
say('walls fed by: %s' % wsrc.name())

def mk(name, ntype):
    n = inst.node(name)
    if n:
        n.destroy()
    return inst.createNode(ntype, name)

fw = mk('frz_walls_read', 'file')
fw.parm('filemode').set(1)
fw.parm('file').set('`chs("../frzpath")`/frz_walls.bgeo.sc')
ff = mk('frz_floor_read', 'file')
ff.parm('filemode').set(1)
ff.parm('file').set('`chs("../frzpath")`/frz_floor.bgeo.sc')

sw = mk('frz_walls_sw', 'switch')
sw.setInput(0, wsrc)
sw.setInput(1, fw)
sw.parm('input').setExpression('ch("../frozen")')
walls.setInput(0, sw)

sf = mk('frz_floor_sw', 'switch')
sf.setInput(0, mp)
sf.setInput(1, ff)
sf.parm('input').setExpression('ch("../frozen")')
stk.setInput(0, sf)

wp = walls.position()
kp = stk.position()
sw.setPosition((wp[0] - 1.0, wp[1] + 1.2))
fw.setPosition((wp[0] + 1.2, wp[1] + 2.4))
sf.setPosition((kp[0] - 1.0, kp[1] + 1.2))
ff.setPosition((kp[0] + 1.2, kp[1] + 2.4))
for n in (sw, sf, fw, ff):
    n.setColor(hou.Color((0.35, 0.65, 0.95)))
say('seams wired: walls <- frz_walls_sw , stk_stack <- frz_floor_sw')

# ---------------------------------------------------------------- parms -----
ptg = inst.parmTemplateGroup()
found = ptg.find('frz_folder')
if found:
    ptg.remove(found)
fld = hou.FolderParmTemplate('frz_folder', 'Freeze', folder_type=hou.folderType.Simple)
b1 = hou.ButtonParmTemplate('frz_freeze', 'FREEZE FLOOR')
b1.setScriptCallback('hou.phm().freeze_floor(kwargs)')
b1.setScriptCallbackLanguage(hou.scriptLanguage.Python)
b2 = hou.ButtonParmTemplate('frz_unfreeze', 'UNFREEZE')
b2.setScriptCallback('hou.phm().unfreeze_floor(kwargs)')
b2.setScriptCallbackLanguage(hou.scriptLanguage.Python)
tg = hou.ToggleParmTemplate('frozen', 'Frozen (skip recook)', default_value=False)
sp = hou.StringParmTemplate('frzpath', 'Freeze Folder', 1,
                            default_value=('$HIP/freeze',),
                            string_type=hou.stringParmType.FileReference,
                            file_type=hou.fileType.Directory)
stt = hou.StringParmTemplate('frzstatus', 'Freeze Status', 1, default_value=('live',))
for t in (b1, b2, tg, sp, stt):
    fld.addParmTemplate(t)
ptg.append(fld)
inst.setParmTemplateGroup(ptg)
say('parms added: frz_freeze, frz_unfreeze, frozen, frzpath, frzstatus')

# ---------------------------------------------------------------- save ------
d = inst.type().definition()
secs = d.sections()
create_script = secs['CreateScript'].contents() if 'CreateScript' in secs else None
pymod         = secs['PythonModule'].contents() if 'PythonModule' in secs else ''
say('CreateScript before: %s bytes' % (len(create_script) if create_script else 'MISSING'))
say('PythonModule before: %d bytes' % len(pymod))
newpm = pymod if 'def freeze_floor' in pymod else (pymod + PYMOD_ADD)

d.updateFromNode(inst)
if create_script is not None:
    d.addSection('CreateScript', create_script)
d.addSection('PythonModule', newpm)
say('CreateScript after : %d bytes' % len(d.sections()['CreateScript'].contents()))
say('PythonModule after : %d bytes' % len(d.sections()['PythonModule'].contents()))

tmp.destroy()

# ---------------------------------------------------------------- verify ----
tv = hou.node('/obj').createNode('geo', 'FRZ_VERIFY')
v  = tv.createNode(TYPE_NAME, 'verify')
v.allowEditingOfContents()
kids = set(c.name() for c in v.allSubChildren())
say('VERIFY: fresh instance has %d nodes' % len(kids))
for nm in ('frz_walls_read', 'frz_floor_read', 'frz_walls_sw', 'frz_floor_sw',
           'ucx_dep', 'ucx_blocks', 'ucx_parts', 'ucx_ceiling', 'ucx_cols',
           'ism_pack', 'curve1', 'walls', 'merge_parts', 'stk_stack'):
    say('   %-16s %s' % (nm, 'ok' if nm in kids else '*** MISSING ***'))
vw = v.node('walls')
vs = v.node('stk_stack')
say('   walls.input0     = %s' % (vw.inputs()[0].name() if vw.inputs() and vw.inputs()[0] else None))
say('   stk_stack.input0 = %s' % (vs.inputs()[0].name() if vs.inputs() and vs.inputs()[0] else None))
say('   new parms found  = %s' % [p for p in ('frz_freeze', 'frz_unfreeze', 'frozen', 'frzpath', 'frzstatus') if v.parm(p)])
say('   frozen default   = %r' % v.evalParm('frozen'))
try:
    v.node('output0').cook(force=True)
    say('   verify cook: ok, errors=%r' % (v.errors(),))
except Exception as e:
    say('   verify cook FAILED: %s' % e)
tv.destroy()
say('file size now: %d bytes' % os.path.getsize(HDA_FILE))

RESULT = '\n'.join(R)
