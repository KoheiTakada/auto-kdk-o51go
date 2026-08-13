#!/usr/bin/env python3
"""Generate a thin-N/S, side-only Tadpole mount version of o51go.

PCB, switch, trackball and original Z geometry are left untouched.  The existing
Auto-KDK STL files are the source of truth.  North/south case overhang is trimmed;
left/right Tadpole pods are added locally at six points.
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
    result = getattr(trimesh.boolean, op)(meshes, engine="manifold")
    if isinstance(result, trimesh.Scene):
        result = trimesh.util.concatenate(tuple(result.geometry.values()))
    if not isinstance(result, trimesh.Trimesh) or not len(result.faces):
        raise RuntimeError(f"Boolean {op} failed")
    result.remove_unreferenced_vertices()
    return result


def box_between(x0, x1, y0, y1, z0, z1):
    ext = np.array([x1-x0, y1-y0, z1-z0], dtype=float)
    T = np.eye(4)
    T[:3, 3] = [(x0+x1)/2, (y0+y1)/2, (z0+z1)/2]
    return trimesh.creation.box(extents=ext, transform=T)


def cyl(d, z0, z1, x, y, sections=64):
    m = trimesh.creation.cylinder(radius=d/2, height=z1-z0, sections=sections)
    m.apply_translation([x, y, (z0+z1)/2])
    return m


def trim_y(m, ymin, ymax):
    b = m.bounds
    clip = box_between(b[0,0]-20, b[1,0]+20, ymin, ymax, b[0,2]-20, b[1,2]+20)
    return boolean("intersection", [m, clip])


def bridge(side, plate_edge_x, center_x, half_y, z0, z1, overlap=0.5):
    if side == "left":
        x0, x1 = center_x, plate_edge_x + overlap
    else:
        x0, x1 = plate_edge_x - overlap, center_x
    if x0 > x1:
        x0, x1 = x1, x0
    return box_between(x0, x1, -half_y, half_y, z0, z1)


def local_bridge(side, plate_edge_x, center_x, y, half_y, z0, z1, overlap=0.6):
    if side == "left":
        x0, x1 = center_x, plate_edge_x + overlap
    else:
        x0, x1 = plate_edge_x - overlap, center_x
    if x0 > x1:
        x0, x1 = x1, x0
    return box_between(x0, x1, y-half_y, y+half_y, z0, z1)


def stats(name, m):
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
                    help="N/S case margin beyond original plate envelope")
    ap.add_argument("--mount-offset-x", type=float, default=4.50,
                    help="Tadpole center distance outboard from plate X edge")
    ap.add_argument("--plate-hole-d", type=float, default=3.05)
    ap.add_argument("--plate-pod-d", type=float, default=6.20)
    ap.add_argument("--top-bore-d", type=float, default=3.05)
    ap.add_argument("--top-pod-d", type=float, default=7.20)
    ap.add_argument("--top-bore-depth", type=float, default=3.00)
    ap.add_argument("--top-roof-min", type=float, default=0.80)
    ap.add_argument("--bottom-pocket-d", type=float, default=4.90)
    ap.add_argument("--bottom-pod-d", type=float, default=7.40)
    ap.add_argument("--bottom-pocket-depth", type=float, default=3.30)
    args = ap.parse_args()

    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    plate = load(repo / "case/o51go-plate.stl")
    top = load(repo / "case/o51go-top-case.stl")
    bottom = load(repo / "case/o51go-bottom-case.stl")
    source = [stats("plate", plate), stats("top", top), stats("bottom", bottom)]
    print("SOURCE", json.dumps(source, indent=2))

    pb, tb, bb = plate.bounds, top.bounds, bottom.bounds
    target_ymin = float(pb[0,1] - args.ns_margin)
    target_ymax = float(pb[1,1] + args.ns_margin)

    # 3 mounts per side.  End mounts stay 8 mm inboard of plate N/S ends.
    ys = np.linspace(float(pb[0,1] + 8.0), float(pb[1,1] - 8.0), 3).tolist()
    centers = {
        "left": float(pb[0,0] - args.mount_offset_x),
        "right": float(pb[1,0] + args.mount_offset_x),
    }
    mounts = [(side, x, float(y)) for side, x in centers.items() for y in ys]

    # First shave only the N/S external footprint.
    top_new = trim_y(top, target_ymin, target_ymax)
    bottom_new = trim_y(bottom, target_ymin, target_ymax)

    pz0, pz1 = map(float, [pb[0,2], pb[1,2]])

    # Plate: add small circular ears + short bridges only at the six mounts.
    plate_add = []
    for side, x, y in mounts:
        edge = float(pb[0,0] if side == "left" else pb[1,0])
        plate_add += [
            cyl(args.plate_pod_d, pz0, pz1, x, y),
            local_bridge(side, edge, x, y, args.plate_pod_d/2, pz0, pz1),
        ]
    plate_new = boolean("union", [plate] + plate_add)
    plate_new = boolean("difference", [plate_new] + [
        cyl(args.plate_hole_d, pz0-1, pz1+1, x, y) for _,x,y in mounts
    ])

    # Top capture: local pods are unioned at plate level; blind D3.05 bores capture
    # the shortened low-profile Tadpole stem.  Only these side locations grow in X.
    top_zmax = float(top_new.bounds[1,2])
    bore_z0 = pz1 - 0.05
    bore_z1 = min(bore_z0 + args.top_bore_depth, top_zmax - args.top_roof_min)
    if bore_z1 <= bore_z0 + 1.0:
        raise RuntimeError(f"Insufficient top Z for Tadpole bore: {bore_z0=}, {bore_z1=}")
    top_add = []
    for side, x, y in mounts:
        edge = float(pb[0,0] if side == "left" else pb[1,0])
        top_add += [
            cyl(args.top_pod_d, bore_z0-0.6, top_zmax, x, y),
            local_bridge(side, edge, x, y, args.top_pod_d/2, bore_z0-0.6, top_zmax),
        ]
    top_new = boolean("union", [top_new] + top_add)
    top_new = boolean("difference", [top_new] + [
        cyl(args.top_bore_d, bore_z0, bore_z1, x, y) for _,x,y in mounts
    ])

    # Bottom capture: 4.9 mm relief pocket with 1.25 mm radial wall in a 7.4 mm pod.
    pocket_z1 = pz0 + 0.05
    pocket_z0 = pz0 - args.bottom_pocket_depth
    bottom_add_z0 = max(float(bottom_new.bounds[0,2]), pocket_z0 - 1.0)
    bottom_add = []
    for side, x, y in mounts:
        edge = float(pb[0,0] if side == "left" else pb[1,0])
        bottom_add += [
            cyl(args.bottom_pod_d, bottom_add_z0, pocket_z1, x, y),
            local_bridge(side, edge, x, y, args.bottom_pod_d/2, bottom_add_z0, pocket_z1),
        ]
    bottom_new = boolean("union", [bottom_new] + bottom_add)
    bottom_new = boolean("difference", [bottom_new] + [
        cyl(args.bottom_pocket_d, pocket_z0, pocket_z1+0.2, x, y) for _,x,y in mounts
    ])

    generated = [stats("plate", plate_new), stats("top", top_new), stats("bottom", bottom_new)]
    if not all(x["watertight"] for x in generated):
        raise RuntimeError(f"Non-watertight output: {generated}")

    for name, mesh in [("plate", plate_new), ("top-case", top_new), ("bottom-case", bottom_new)]:
        mesh.export(out / f"o51go-tadpole-thin-ns-{name}.stl")

    scene = trimesh.Scene()
    scene.add_geometry(bottom_new, node_name="bottom-case", geom_name="bottom-case")
    scene.add_geometry(plate_new, node_name="plate", geom_name="plate")
    scene.add_geometry(top_new, node_name="top-case", geom_name="top-case")
    scene.export(out / "o51go-tadpole-thin-ns-assembly.glb")

    report = {
        "design_intent": {
            "pcb_modified": False,
            "switch_trackball_layout_modified": False,
            "north_south_margin_reduced": True,
            "lateral_growth_only_at_tadpole_pods": True,
            "mount_count": 6,
        },
        "parameters_mm": {
            "north_south_margin_beyond_plate": args.ns_margin,
            "target_ymin": target_ymin,
            "target_ymax": target_ymax,
            "mount_offset_x": args.mount_offset_x,
            "plate_hole_d": args.plate_hole_d,
            "plate_pod_d": args.plate_pod_d,
            "top_bore_d": args.top_bore_d,
            "top_bore_depth_actual": round(bore_z1-bore_z0, 3),
            "top_pod_d": args.top_pod_d,
            "bottom_pocket_d": args.bottom_pocket_d,
            "bottom_pocket_depth": args.bottom_pocket_depth,
            "bottom_pod_d": args.bottom_pod_d,
        },
        "mount_centers_mm": [
            {"side": side, "x": round(x,3), "y": round(y,3)} for side,x,y in mounts
        ],
        "source": source,
        "generated": generated,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
