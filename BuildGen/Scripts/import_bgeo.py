import hou
import os

# --- /obj/geo1 ---
obj = hou.node("/obj")
geo1 = obj.node("geo1") or obj.createNode("geo", "geo1")

# --- subnet-container for meshes (subnet, NOT null!) ---
subnet = geo1.node("Meshes") or geo1.createNode("subnet", "Meshes")

# --- BGEO import ---
folder_path = hou.expandString("$HIP/geo")

if not os.path.isdir(folder_path):
    raise hou.Error("Invalid folder path: " + folder_path)

bgeo_files = [
    os.path.join(folder_path, f)
    for f in os.listdir(folder_path)
    if f.lower().endswith(".bgeo.sc")
]

if not bgeo_files:
    raise hou.Error("No .bgeo.sc files found in: " + folder_path)

for bgeo in sorted(bgeo_files):
    file_sop = subnet.createNode("file")
    file_sop.parm("file").set(bgeo)

    name = os.path.basename(bgeo)
    if name.lower().endswith(".bgeo.sc"):
        name = name[:-len(".bgeo.sc")]
    file_sop.setName(name, unique_name=True)

subnet.layoutChildren()
print("Imported %d bgeo files into %s" % (len(bgeo_files), subnet.path()))
