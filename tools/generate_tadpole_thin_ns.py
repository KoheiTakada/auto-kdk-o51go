#!/usr/bin/env python3
"""Generate a side-only Tadpole mount version of o51go.

Goals
- Keep PCB / switch / trackball layout untouched.
- Keep the original Auto-KDK Z geometry and left/right case contour as much as possible.
- Reduce ONLY north/south (top/bottom in plan view) exterior margin.
- Put Tadpole mounts only in the existing left/right side margin.

The source STL files are used as the source of truth.  The top and bottom cases are
trimmed by two Y planes, then Tadpole bores/pockets are cut.  The plate itself is
not regenerated; only six D3.0 holes are cut in its side margins.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def load(path: Path) -> trimesh.Trimesh:
    m = trimesh.load_mesh(path, force="mesh", process=True)
    if isinstance(m, trimesh.Scene):
        m = trimesh.util.concatenate(tuple(m.geometry.values()))
    if not isinstance(m, trimesh.Trimesh):
        raise RuntimeError(f"Failed to load {path}")
    m.remove_unreferenced_vertices()
    return m


def boolean(op: str, meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    fn = getattr(trimesh.boolean, op)
    result = fn(meshes, engine="manifold")
    if isinstance(result, trimesh.Scene):
        result = trimesh.util.concatenate(tuple(result.geometry.values()))
    if not isinstance(result, trimesh.Trimesh) or len(result.faces) == 0:
        raise RuntimeError(f"Boolean {op} failed")
    result.remove_unreferenced_vertices()
    return result


def box_between(x0, x1, y0, y1, z0, z1):
    ext = np.array([x1-x0, y1-y0, z1-z0], dtype=float)
    T = np.eye(4)
    T[:3, 3] = [(x0+x1)/2, (y0+y1)/2, (z0+z1)/2]
    return trimesh.creation.box(extents=ext, transform=T)


def cyl(d: float, z0: float, z1: float, x: float, y: float, sections=64):
    m = trimesh.creation.cylinder(radius=d/2, height=z1-z0, sections=sections)
    m.apply_translation([x, y, (z0+z1)/2])
    return m


def trim_y(m: trimesh.Trimesh, ymin: float, ymax: float) -> trimesh.Trimesh:
    b = m.bounds
    pad = 20.0
    clip = box_between(
        b[0,0]-pad, b[1,0]+pad,
        ymin, ymax,
        b[0,2]-pad, b[1,2]+pad,
    )
    return boolean("intersection", [m, clip])


def mesh_stats(name: str, m: trimesh.Trimesh):
    b = m.bounds
    return {
        "name": name,
        "bounds_mm": np.round(b, 3).tolist(),
        "size_mm": np.round(b[1]-b[0], 3).tolist(),
        "faces": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
        "volume_mm3": round(float(m.volume), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, default=Path("tadpole-output"))
    ap.add_argument("--ns-margin", type=float, default=1.20,
                    help="Case N/S margin beyond original plate envelope, mm")
    ap.add_argument("--mount-inset-x", type=float, default=4.50,
                    help="Tadpole center distance outboard from plate X edge, mm")
    ap.add_argument("--plate-hole-d", type=float, default=3.05)
    ap.add_argument("--top-bore-d", type=float, default=3.05)
    ap.add_argument("--top-bore-depth", type=float, default=3.00,
                    help="Low-profile bore depth; assumes Tadpole stem shortened about 2mm")
    ap.add_argument("--top-roof-min", type=float, default=0.80)
    ap.add_argument("--bottom-pocket-d", type=float, default=4.90)
    ap.add_argument("--bottom-pocket-depth", type=float, default=3.30,
                    help="3.1mm Tadpole lower height + 0.2mm clearance")
    args = ap.parse_args()

    repo = args.repo.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    src = {
        "plate": repo / "case/o51go-plate.stl",
        "top": repo / "case/o51go-top-case.stl",
        "bottom": repo / "case/o51go-bottom-case.stl",
    }
    for p in src.values():
        if not p.exists():
            raise FileNotFoundError(p)

    plate = load(src["plate"])
    top = load(src["top"])
    bottom = load(src["bottom"])
    source_stats = [mesh_stats("plate", plate), mesh_stats("top", top), mesh_stats("bottom", bottom)]

    pb, tb, bb = plate.bounds, top.bounds, bottom.bounds
    target_ymin = float(pb[0,1] - args.ns_margin)
    target_ymax = float(pb[1,1] + args.ns_margin)

    # Six mounts: three on each side.  Keep them well away from the newly-thin N/S edges.
    usable_ymin = float(pb[0,1] + 8.0)
    usable_ymax = float(pb[1,1] - 8.0)
    ys = np.linspace(usable_ymin, usable_ymax, 3).tolist()
    mount_x = {
        "left": float(pb[0,0] - args.mount_inset_x),
        "right": float(pb[1,0] + args.mount_inset_x),
    }
    mounts = [(side, x, float(y)) for side, x in mount_x.items() for y in ys]

    # Fail early if current side margin is insufficient.  This keeps the generator from silently
    # altering PCB geometry or making a weak open edge.  If it fails, the next revision adds side pods.
    required_side = args.bottom_pocket_d/2 + 1.0
    if mount_x["left"] - required_side < max(tb[0,0], bb[0,0]):
        raise RuntimeError("Left side margin is too small for the Tadpole pocket")
    if mount_x["right"] + required_side > min(tb[1,0], bb[1,0]):
        raise RuntimeError("Right side margin is too small for the Tadpole pocket")

    # N/S reduction: trim complete original solids.  Manifold boolean closes the new cut planes,
    # preserving a printable solid instead of leaving an open STL shell.
    top_new = trim_y(top, target_ymin, target_ymax)
    bottom_new = trim_y(bottom, target_ymin, target_ymax)

    # Plate holes.  Source plate thickness is retained exactly.
    pz0, pz1 = float(pb[0,2]), float(pb[1,2])
    plate_cutters = [cyl(args.plate_hole_d, pz0-1, pz1+1, x, y) for _,x,y in mounts]
    plate_new = boolean("difference", [plate] + plate_cutters)

    # Top: D3.0 stem is captured in a blind bore.  For the low-profile o51go case the standard
    # 5mm stem engagement is shortened about 2mm, matching Auto-KDK's low-profile Tadpole note.
    top_zmax = float(top_new.bounds[1,2])
    bore_z0 = pz1 - 0.05
    requested_bore_z1 = bore_z0 + args.top_bore_depth
    bore_z1 = min(requested_bore_z1, top_zmax - args.top_roof_min)
    if bore_z1 <= bore_z0 + 1.0:
        raise RuntimeError(f"Insufficient top-case Z for blind Tadpole bore: {bore_z0=}, {bore_z1=}")
    top_cutters = [cyl(args.top_bore_d, bore_z0, bore_z1, x, y) for _,x,y in mounts]
    top_new = boolean("difference", [top_new] + top_cutters)

    # Bottom: Tadpole drawing gives 3.1mm below plate and 0.2mm clearance to the pocket floor.
    pocket_z1 = pz0 + 0.05
    pocket_z0 = pz0 - args.bottom_pocket_depth
    bottom_cutters = [cyl(args.bottom_pocket_d, pocket_z0, pocket_z1, x, y) for _,x,y in mounts]
    bottom_new = boolean("difference", [bottom_new] + bottom_cutters)

    for name, mesh in [("plate", plate_new), ("top-case", top_new), ("bottom-case", bottom_new)]:
        mesh.export(out / f"o51go-tadpole-thin-ns-{name}.stl")

    # Assembly preview: separate bodies in original coordinates, useful in slicer/CAD inspection.
    scene = trimesh.Scene()
    scene.add_geometry(bottom_new, node_name="bottom-case", geom_name="bottom-case")
    scene.add_geometry(plate_new, node_name="plate", geom_name="plate")
    scene.add_geometry(top_new, node_name="top-case", geom_name="top-case")
    scene.export(out / "o51go-tadpole-thin-ns-assembly.glb")

    result_stats = [mesh_stats("plate", plate_new), mesh_stats("top", top_new), mesh_stats("bottom", bottom_new)]
    report = {
        "design_intent": {
            "pcb_modified": False,
            "north_south_only_reduced": True,
            "side_mounts_only": True,
            "mount_count": 6,
        },
        "parameters_mm": {
            "north_south_margin_beyond_plate": args.ns_margin,
            "target_ymin": target_ymin,
            "target_ymax": target_ymax,
            "plate_hole_d": args.plate_hole_d,
            "top_bore_d": args.top_bore_d,
            "top_bore_depth_actual": bore_z1-bore_z0,
            "bottom_pocket_d": args.bottom_pocket_d,
            "bottom_pocket_depth": args.bottom_pocket_depth,
        },
        "mount_centers_mm": [
            {"side": side, "x": round(x,3), "y": round(y,3)} for side,x,y in mounts
        ],
        "source": source_stats,
        "generated": result_stats,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
