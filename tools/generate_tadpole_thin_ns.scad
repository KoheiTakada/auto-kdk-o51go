// o51go thin north/south + side-only Tadpole mount generator
// PCB, switch positions, trackball position, and Z geometry are unchanged.
// Source geometry: existing Auto-KDK STL files in ../case/.

$fn = 64;
part = "plate"; // override with: -D 'part="top"'

plate_src = "../case/o51go-plate.stl";
top_src = "../case/o51go-top-case.stl";
bottom_src = "../case/o51go-bottom-case.stl";

// Measured directly from the switch apertures of o51go-plate.stl.
switch_y_min = -36.075;
switch_y_max = 35.550;
plate_ns_margin = 2.000;
case_ns_margin = 1.200;

plate_y_min = switch_y_min - plate_ns_margin;
plate_y_max = switch_y_max + plate_ns_margin;
case_y_min = plate_y_min - case_ns_margin;
case_y_max = plate_y_max + case_ns_margin;

// Original plate X bounds and six side-only Tadpole locations.
plate_x_min = -129.2;
plate_x_max = 129.2;
mount_offset_x = 4.5;
mount_x = [plate_x_min - mount_offset_x, plate_x_max + mount_offset_x];
mount_end_inset = 5.0;
mount_y = [
    switch_y_min + mount_end_inset,
    (switch_y_min + switch_y_max) / 2,
    switch_y_max - mount_end_inset
];

module crop_y(y0, y1) {
    translate([-180, y0, -40]) cube([360, y1-y0, 70]);
}

module z_cylinder(d, z0, z1, x, y) {
    translate([x, y, z0]) cylinder(d=d, h=z1-z0);
}

module side_bridge(side, edge_x, center_x, center_y, half_y, z0, z1, overlap=0.6) {
    x0 = side < 0 ? center_x : edge_x - overlap;
    x1 = side < 0 ? edge_x + overlap : center_x;
    translate([min(x0,x1), center_y-half_y, z0])
        cube([abs(x1-x0), 2*half_y, z1-z0]);
}

module plate_base() {
    intersection() {
        import(plate_src, convexity=30);
        crop_y(plate_y_min, plate_y_max);
    }
}

module top_base() {
    intersection() {
        import(top_src, convexity=30);
        crop_y(case_y_min, case_y_max);
    }
}

module bottom_base() {
    intersection() {
        import(bottom_src, convexity=30);
        crop_y(case_y_min, case_y_max);
    }
}

module final_plate() {
    difference() {
        union() {
            plate_base();
            for (side=[-1,1]) for (y=mount_y) {
                x = side < 0 ? mount_x[0] : mount_x[1];
                edge = side < 0 ? plate_x_min : plate_x_max;
                z_cylinder(6.20, 0.0, 2.9, x, y);
                side_bridge(side, edge, x, y, 3.10, 0.0, 2.9);
            }
        }
        for (x=mount_x) for (y=mount_y)
            z_cylinder(3.05, -1.0, 3.9, x, y);
    }
}

module final_top() {
    difference() {
        union() {
            top_base();
            for (side=[-1,1]) for (y=mount_y) {
                x = side < 0 ? mount_x[0] : mount_x[1];
                // Original top-case X limit is +/-132 mm.
                edge = side < 0 ? -132.0 : 132.0;
                z_cylinder(7.20, 2.25, 7.20, x, y);
                side_bridge(side, edge, x, y, 3.60, 2.25, 7.20);
            }
        }
        for (x=mount_x) for (y=mount_y)
            z_cylinder(3.05, 2.85, 5.85, x, y);
    }
}

module final_bottom() {
    difference() {
        union() {
            bottom_base();
            for (side=[-1,1]) for (y=mount_y) {
                x = side < 0 ? mount_x[0] : mount_x[1];
                edge = side < 0 ? plate_x_min : plate_x_max;
                z_cylinder(7.40, -4.30, 0.05, x, y);
                side_bridge(side, edge, x, y, 3.70, -4.30, 0.05);
            }
        }
        for (x=mount_x) for (y=mount_y)
            z_cylinder(4.90, -3.30, 0.25, x, y);
    }
}

if (part == "plate") final_plate();
else if (part == "top") final_top();
else if (part == "bottom") final_bottom();
