# -*- coding: utf-8 -*-
# Second half of the FREEZE install: put the Freeze folder onto the TYPE's
# parameter interface. Writing it through an unlocked instance did not stick;
# HDADefinition.setParmTemplateGroup is the route that does.
import hou, os

R = []
def say(s): R.append(str(s))

t  = hou.nodeType(hou.sopNodeTypeCategory(), 'buildgen')
dd = t.definition()
HDA_FILE = dd.libraryFilePath()

secs = dd.sections()
create_script = secs['CreateScript'].contents() if 'CreateScript' in secs else None
pymod         = secs['PythonModule'].contents() if 'PythonModule' in secs else ''
say('before: CreateScript %s b, PythonModule %d b, file %d b'
    % (len(create_script) if create_script else 'MISSING', len(pymod), os.path.getsize(HDA_FILE)))
say('PythonModule has freeze_floor: %s' % ('def freeze_floor' in pymod))

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
for x in (b1, b2, tg, sp, stt):
    fld.addParmTemplate(x)

ptg = dd.parmTemplateGroup()
old = ptg.find('frz_folder')
if old:
    ptg.remove(old)
ptg.append(fld)
dd.setParmTemplateGroup(ptg)

# setParmTemplateGroup rewrites DialogScript and can drop CreateScript, which is
# where every default parameter value of a fresh instance lives.
if create_script is not None and len(dd.sections().get('CreateScript', dd.sections().get('DialogScript')).contents()) != len(create_script):
    pass
if create_script is not None:
    dd.addSection('CreateScript', create_script)
if 'def freeze_floor' in pymod:
    dd.addSection('PythonModule', pymod)

say('after : CreateScript %d b, PythonModule %d b, file %d b'
    % (len(dd.sections()['CreateScript'].contents()),
       len(dd.sections()['PythonModule'].contents()),
       os.path.getsize(HDA_FILE)))

# ---------------------------------------------------------------- verify ----
for nm in ('/obj/FRZ_VERIFY', '/obj/FRZ_VERIFY2'):
    o = hou.node(nm)
    if o:
        o.destroy()
tv = hou.node('/obj').createNode('geo', 'FRZ_VERIFY2')
v  = tv.createNode('buildgen', 'verify')
v.allowEditingOfContents()
kids = set(c.name() for c in v.allSubChildren())
say('VERIFY: %d nodes' % len(kids))
for n in ('frz_walls_read', 'frz_floor_read', 'frz_walls_sw', 'frz_floor_sw',
          'ucx_dep', 'ucx_blocks', 'ucx_parts', 'ucx_ceiling', 'ucx_cols',
          'ism_pack', 'curve1', 'walls', 'merge_parts', 'stk_stack'):
    say('   %-16s %s' % (n, 'ok' if n in kids else '*** MISSING ***'))

vw, vs = v.node('walls'), v.node('stk_stack')
say('   walls.input0     = %s' % (vw.inputs()[0].name() if vw.inputs() and vw.inputs()[0] else None))
say('   stk_stack.input0 = %s' % (vs.inputs()[0].name() if vs.inputs() and vs.inputs()[0] else None))
for sname in ('frz_walls_sw', 'frz_floor_sw'):
    s = v.node(sname)
    ins = [i.name() if i else None for i in s.inputs()]
    say('   %s inputs=%s  input-expr=%r  eval=%r'
        % (sname, ins, s.parm('input').rawValue(), s.parm('input').eval()))
for fname in ('frz_walls_read', 'frz_floor_read'):
    f = v.node(fname)
    say('   %s file=%r -> %r  filemode=%r'
        % (fname, f.parm('file').rawValue(), f.parm('file').eval(), f.parm('filemode').eval()))

say('   parms on instance = %s'
    % [p for p in ('frz_freeze', 'frz_unfreeze', 'frozen', 'frzpath', 'frzstatus') if v.parm(p)])
if v.parm('frozen'):
    say('   frozen default = %r' % v.evalParm('frozen'))
    say('   frzpath default = %r' % v.evalParm('frzpath'))
    say('   frzstatus default = %r' % v.evalParm('frzstatus'))
say('   callbacks: freeze=%r unfreeze=%r'
    % (v.parm('frz_freeze').parmTemplate().scriptCallback() if v.parm('frz_freeze') else None,
       v.parm('frz_unfreeze').parmTemplate().scriptCallback() if v.parm('frz_unfreeze') else None))
say('   phm has freeze_floor: %s' % hasattr(v.hdaModule(), 'freeze_floor'))
say('   phm has unfreeze_floor: %s' % hasattr(v.hdaModule(), 'unfreeze_floor'))

# a fresh empty instance must still cook clean
try:
    v.node('output0').cook(force=True)
    say('   verify cook: ok, errors=%r' % (v.errors(),))
except Exception as e:
    say('   verify cook FAILED: %s' % e)

# sanity: a few known defaults must survive CreateScript restore
for pn in ('floors', 'blocksdir', 'closedist', 'floorinset', 'ceilthick'):
    if v.parm(pn):
        say('   default %-10s = %r' % (pn, v.evalParm(pn)))

tv.destroy()
say('file size final = %d' % os.path.getsize(HDA_FILE))
RESULT = '\n'.join(R)
