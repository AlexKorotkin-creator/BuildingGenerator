import hou
import os

# Writes next to the currently open scene file, so it works wherever the project is unpacked.
output_dir = hou.expandString("$HIP/geo")
os.makedirs(output_dir, exist_ok=True)

selected = hou.selectedNodes()
if not selected:
    raise hou.Error("Save From UE5: select the imported subnet first, then run the tool.")

subnet = selected[0]

saved = 0
for geo_node in subnet.children():
    if geo_node.type().name() != "geo":
        continue

    # Find the final SOP (usually object_merge or its display node)
    sop = geo_node.displayNode()
    if sop is None:
        continue

    geo = sop.geometry()
    if geo is None:
        continue

    file_path = os.path.join(output_dir, "{}.bgeo.sc".format(geo_node.name()))
    geo.saveToFile(file_path)
    saved += 1
    print("Saved:", file_path)

print("Save From UE5: {} geo node(s) written to {}".format(saved, output_dir))
