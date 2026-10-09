# -*- coding: utf-8 -*-
# Staged FREEZE for BuildGen, per Alex's workflow (09-09-2026).
#
# One Freeze/Unfreeze pair per stage, placed INSIDE the tab that owns that
# stage's parameters - the same placement as the working 'Apply Slab Curve To
# Type' button. The previous pair sat in a Simple folder appended after all the
# tabs and came out greyed in Unreal; that folder is removed here.
#
# Freezing = hard lock on the node that terminates the stage's branch. No new
# nodes, so Contents.gz is untouched: no Reimport, no Rebuild, the built storey
# is not disturbed.
import hou

R = []
def say(s): R.append(str(s))

MARK = '# ---------------------------------------------------------------- FREEZE ----'

NEW = MARK + '''
# Stage order follows the graph, which follows the way the storey is built:
#   blocks     ue_walls      blk_copy / blk_var / blk_xform / blk_rest / blk_library
#   floorceil  floor_mat + ceiling_gate    contour triangulation, slab, ceiling
#   columns    col_gate      column grid, clipping, copies
#   stairs     ss_mir_gate   stairs, shafts, elevator car
#   storey     merge_parts   the whole storey, ready to be stacked upward
#
# A locked node holds its cooked geometry and never asks upstream again, while
# everything below it keeps running. Unfreezing a stage also unfreezes every
# stage after it - otherwise you get old columns standing on new walls.

FRZ_STAGES = (
    ('blocks',    ('ue_walls',)),
    ('floorceil', ('floor_mat', 'ceiling_gate')),
    ('columns',   ('col_gate',)),
    ('stairs',    ('ss_mir_gate',)),
    ('storey',    ('merge_parts',)),
)

def _frz_index(key):
    for i, (k, _n) in enumerate(FRZ_STAGES):
        if k == key:
            return i
    return -1

def _frz_nodes(node, key):
    i = _frz_index(key)
    if i < 0:
        return []
    out = []
    for nm in FRZ_STAGES[i][1]:
        n = node.node(nm)
        if n is not None:
            out.append(n)
    return out

def _frz_say(node, key, text):
    p = node.parm('frz_%s_status' % key)
    if p is not None:
        p.set(text)

def _frz_locked(node, key):
    ns = _frz_nodes(node, key)
    return bool(ns) and all(n.isHardLocked() for n in ns)

def freeze_stage(kwargs, key):
    node = kwargs['node']
    ns = _frz_nodes(node, key)
    if not ns:
        _frz_say(node, key, 'ERROR - stage nodes not found')
        return
    if all(n.isHardLocked() for n in ns):
        _frz_say(node, key, 'already frozen')
        return
    total = 0
    for n in ns:
        g = n.geometry()
        if g is None:
            _frz_say(node, key, 'ERROR - %s has no geometry' % n.name())
            return
        total += len(g.prims())
    if total == 0:
        _frz_say(node, key, 'nothing to freeze - build this stage first')
        return
    for n in ns:
        n.setHardLocked(True)
    _frz_say(node, key, 'FROZEN - %d prims (%s)'
             % (total, ', '.join(n.name() for n in ns)))

def unfreeze_stage(kwargs, key):
    node = kwargs['node']
    i = _frz_index(key)
    if i < 0:
        return
    # cascade: this stage and every stage after it
    for k, _n in FRZ_STAGES[i:]:
        for n in _frz_nodes(node, k):
            n.setHardLocked(False)
        _frz_say(node, k, 'live')

def freeze_report(node):
    return dict((k, _frz_locked(node, k)) for k, _n in FRZ_STAGES)

# kept so any older button still resolves
def freeze_floor(kwargs):
    freeze_stage(kwargs, 'storey')

def unfreeze_floor(kwargs):
    unfreeze_stage(kwargs, 'blocks')
'''

STAGES = [
    ('blocks',    'Freeze  \\u2014  Blocks',            'FREEZE BLOCKS',      'UNFREEZE BLOCKS'),
    ('floorceil', 'Freeze  \\u2014  Floor / Ceiling',   'FREEZE FLOOR+CEIL',  'UNFREEZE FLOOR+CEIL'),
    ('columns',   'Freeze  \\u2014  Columns',           'FREEZE COLUMNS',     'UNFREEZE COLUMNS'),
    ('stairs',    'Freeze  \\u2014  Stairs / Elevator', 'FREEZE STAIRS',      'UNFREEZE STAIRS'),
    ('storey',    'Freeze  \\u2014  Whole Storey',      'FREEZE STOREY',      'UNFREEZE STOREY'),
]

def make_folder(key, label, flab, ulab):
    f = hou.FolderParmTemplate('frz_%s_folder' % key, label,
                               folder_type=hou.folderType.Collapsible)
    b1 = hou.ButtonParmTemplate('frz_%s_freeze' % key, flab)
    b1.setScriptCallback("hou.phm().freeze_stage(kwargs, '%s')" % key)
    b1.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    b2 = hou.ButtonParmTemplate('frz_%s_unfreeze' % key, ulab)
    b2.setScriptCallback("hou.phm().unfreeze_stage(kwargs, '%s')" % key)
    b2.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    st = hou.StringParmTemplate('frz_%s_status' % key, 'Status', 1,
                                default_value=('live',))
    f.addParmTemplate(b1)
    f.addParmTemplate(b2)
    f.addParmTemplate(st)
    return f

t  = hou.nodeType(hou.sopNodeTypeCategory(), 'buildgen')
dd = t.definition()
secs = dd.sections()
create_script = secs['CreateScript'].contents() if 'CreateScript' in secs else None
pm = secs['PythonModule'].contents()
say('PythonModule before = %d b, CreateScript = %s b'
    % (len(pm), len(create_script) if create_script else 'MISSING'))

i = pm.find(MARK)
newpm = (pm[:i].rstrip() if i != -1 else pm.rstrip()) + '\n\n\n' + NEW
say('PythonModule rebuilt = %d b (marker %s)' % (len(newpm), 'found' if i != -1 else 'absent'))

ptg = dd.parmTemplateGroup()

# drop the greyed-out Simple folder from the first attempt
old = ptg.find('frz_folder')
if old:
    ptg.remove(old)
    say('removed old frz_folder (Simple, after all tabs)')

folders = dict((k, make_folder(k, lab.encode().decode('unicode_escape'), f, u))
               for k, lab, f, u in STAGES)

def place(key, how, anchor):
    tmpl = folders[key]
    a = ptg.find(anchor)
    if a is None:
        say('  ! anchor %r not found for stage %s' % (anchor, key))
        return False
    if how == 'before':
        ptg.insertBefore(a, tmpl)
    elif how == 'after':
        ptg.insertAfter(a, tmpl)
    else:
        ptg.appendToFolder(a, tmpl)
    say('  placed %-9s %s %s' % (key, how, anchor))
    return True

place('blocks',    'before', 'closeloop')            # Floors / Blocks tab
place('floorceil', 'after',  'makeceiling')          # Floors / Blocks tab
place('columns',   'after',  'colwidth')             # Columns tab
place('stairs',    'append', 'tab_floors7_1')        # Stairs / Elevator tab
place('storey',    'append', 'tab_floors7')          # Floors / Blocks tab, at the end

dd.setParmTemplateGroup(ptg)
dd.addSection('PythonModule', newpm)
if create_script is not None and dd.sections()['CreateScript'].contents() != create_script:
    dd.addSection('CreateScript', create_script)
    say('CreateScript restored')
say('after: PythonModule=%d b CreateScript=%d b sections=%s'
    % (len(dd.sections()['PythonModule'].contents()),
       len(dd.sections()['CreateScript'].contents()),
       sorted(dd.sections().keys())))

# ------------------------------------------------------------------ verify --
old = hou.node('/obj/FRZ_CHECK')
if old:
    old.destroy()
tv = hou.node('/obj').createNode('geo', 'FRZ_CHECK')
v = tv.createNode('buildgen', 'chk')
v.allowEditingOfContents()
say('VERIFY on a fresh instance: %d nodes' % len(v.allSubChildren()))
for k, _lab, _f, _u in STAGES:
    ok = []
    for suf in ('freeze', 'unfreeze', 'status'):
        pn = 'frz_%s_%s' % (k, suf)
        p = v.parm(pn)
        ok.append('%s=%s' % (suf, 'ok' if p else 'MISSING'))
    p = v.parm('frz_%s_freeze' % k)
    fold = p.containingFolders() if p else None
    say('   %-9s %s  folders=%s' % (k, ' '.join(ok), fold))
say('   frz_folder gone: %s' % (v.parm('frz_freeze') is None))
say('   old frozen parm: %s' % ('still there' if v.parm('frozen') else 'gone'))
m = v.hdaModule()
say('   phm: freeze_stage=%s unfreeze_stage=%s freeze_report=%s'
    % (hasattr(m, 'freeze_stage'), hasattr(m, 'unfreeze_stage'), hasattr(m, 'freeze_report')))
say('   stage nodes present: %s'
    % [nm for nm in ('ue_walls', 'floor_mat', 'ceiling_gate', 'col_gate', 'ss_mir_gate', 'merge_parts')
       if v.node(nm) is not None])
try:
    v.node('output0').cook(force=True)
    say('   verify cook: ok, errors=%r' % (v.errors(),))
except Exception as e:
    say('   verify cook FAILED: %s' % e)
tv.destroy()

# ------------------------------------------------------- the live generator --
n = hou.node('/obj/buildgen/buildgen1')
if n:
    m = n.hdaModule()
    say('LIVE proxy: phm freeze_stage=%s' % hasattr(m, 'freeze_stage'))
    say('LIVE proxy: new parms = %s'
        % [k for k, _l, _f, _u in STAGES if n.parm('frz_%s_freeze' % k)])
    say('LIVE proxy: locks now = %s' % (m.freeze_report(n) if hasattr(m, 'freeze_report') else 'n/a'))
    for nm in ('ue_walls', 'floor_mat', 'ceiling_gate', 'col_gate', 'ss_mir_gate', 'merge_parts'):
        nd = n.node(nm)
        say('   %-13s exists=%s locked=%s' % (nm, nd is not None, nd.isHardLocked() if nd else '-'))
RESULT = '\n'.join(R)
