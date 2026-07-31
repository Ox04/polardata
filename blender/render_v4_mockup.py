from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/design-v4"
YEAR = 2013

BACKGROUND = (0.004, 0.012, 0.019, 1.0)
COLORS = {
    1: (0.025, 0.120, 0.380, 1.0),
    2: (0.030, 0.260, 0.520, 1.0),
    3: (0.050, 0.470, 0.600, 1.0),
    4: (0.250, 0.670, 0.680, 1.0),
    5: (0.820, 0.850, 0.690, 1.0),
    20: (0.014, 0.024, 0.031, 1.0),
}
HEIGHTS = {
    1: 0.04,
    2: 0.08,
    3: 0.14,
    4: 0.22,
    5: 0.32,
    20: 0.012,
}


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    node = result.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = color
    is_land = name == "land" or name.endswith("-20-20")
    node.inputs["Roughness"].default_value = 0.86 if is_land else 0.48
    node.inputs["Metallic"].default_value = 0.03
    if not is_land:
        node.inputs["Emission Color"].default_value = color
        node.inputs["Emission Strength"].default_value = 0.06
    return result


def create_block_relief(classes: np.ndarray) -> bpy.types.Object:
    rows, columns = classes.shape
    scale = 13.0 / max(rows, columns)
    radius = min(rows, columns) * 0.485
    center_row = (rows - 1) / 2
    center_column = (columns - 1) / 2

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    face_materials: list[int] = []
    material_order = (20, 1, 2, 3, 4, 5)
    material_index = {value: index for index, value in enumerate(material_order)}

    def visible(row: int, column: int) -> bool:
        if row < 0 or row >= rows or column < 0 or column >= columns:
            return False
        distance = math.hypot(row - center_row, column - center_column)
        return distance <= radius and int(classes[row, column]) in HEIGHTS

    def height_at(row: int, column: int) -> float:
        if not visible(row, column):
            return 0.0
        return HEIGHTS[int(classes[row, column])]

    def add_face(points: list[tuple[float, float, float]], index: int) -> None:
        start = len(vertices)
        vertices.extend(points)
        faces.append((start, start + 1, start + 2, start + 3))
        face_materials.append(index)

    for row in range(rows):
        for column in range(columns):
            if not visible(row, column):
                continue
            value = int(classes[row, column])
            height = HEIGHTS[value]
            x0 = (column - center_column - 0.5) * scale
            x1 = x0 + scale
            y1 = (center_row - row + 0.5) * scale
            y0 = y1 - scale
            index = material_index[value]
            add_face(
                [(x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height)],
                index,
            )

            neighbors = (
                (-1, 0, [(x0, y1), (x1, y1)]),
                (1, 0, [(x1, y0), (x0, y0)]),
                (0, -1, [(x0, y0), (x0, y1)]),
                (0, 1, [(x1, y1), (x1, y0)]),
            )
            for delta_row, delta_column, edge in neighbors:
                neighbor_height = height_at(row + delta_row, column + delta_column)
                if neighbor_height >= height:
                    continue
                (ax, ay), (bx, by) = edge
                add_face(
                    [
                        (ax, ay, neighbor_height),
                        (bx, by, neighbor_height),
                        (bx, by, height),
                        (ax, ay, height),
                    ],
                    index,
                )

    mesh = bpy.data.meshes.new("arctic-age-relief")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    relief = bpy.data.objects.new("arctic-age-relief", mesh)
    bpy.context.collection.objects.link(relief)
    relief.rotation_euler[2] = math.radians(-10)

    for value in material_order:
        name = "land" if value == 20 else f"age-{value}"
        relief.data.materials.append(material(name, COLORS[value]))
    for polygon, index in zip(relief.data.polygons, face_materials):
        polygon.material_index = index
        polygon.use_smooth = False
    return relief


def create_transition_relief(
    first: np.ndarray,
    second: np.ndarray,
    amount: float,
) -> bpy.types.Object:
    if first.shape != second.shape:
        raise ValueError("Transition grids must have the same shape")

    rows, columns = first.shape
    scale = 13.0 / max(rows, columns)
    radius = min(rows, columns) * 0.485
    center_row = (rows - 1) / 2
    center_column = (columns - 1) / 2

    def ice_height(value: int) -> float:
        return HEIGHTS.get(value, 0.0) if value != 20 else HEIGHTS[20]

    def height_at(row: int, column: int) -> float:
        if row < 0 or row >= rows or column < 0 or column >= columns:
            return 0.0
        if math.hypot(row - center_row, column - center_column) > radius:
            return 0.0
        first_value = int(first[row, column])
        second_value = int(second[row, column])
        if first_value == 20 and second_value == 20:
            return HEIGHTS[20]
        return (
            ice_height(first_value) * (1 - amount)
            + ice_height(second_value) * amount
        )

    def visible(row: int, column: int) -> bool:
        return height_at(row, column) > 0.002

    def color_pair(row: int, column: int) -> tuple[int, int]:
        return int(first[row, column]), int(second[row, column])

    def mixed_color(pair: tuple[int, int]) -> tuple[float, float, float, float]:
        first_value, second_value = pair
        if first_value == 20 and second_value == 20:
            return COLORS[20]
        first_color = COLORS.get(first_value)
        second_color = COLORS.get(second_value)
        if first_color is None:
            return second_color or COLORS[1]
        if second_color is None:
            return first_color
        return first_color if amount < 0.5 else second_color

    material_order = sorted(
        {
            color_pair(row, column)
            for row in range(rows)
            for column in range(columns)
            if visible(row, column)
        }
    )
    material_index = {
        pair: index for index, pair in enumerate(material_order)
    }

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    face_materials: list[int] = []

    def add_face(points: list[tuple[float, float, float]], index: int) -> None:
        start = len(vertices)
        vertices.extend(points)
        faces.append((start, start + 1, start + 2, start + 3))
        face_materials.append(index)

    for row in range(rows):
        for column in range(columns):
            if not visible(row, column):
                continue
            height = height_at(row, column)
            x0 = (column - center_column - 0.5) * scale
            x1 = x0 + scale
            y1 = (center_row - row + 0.5) * scale
            y0 = y1 - scale
            index = material_index[color_pair(row, column)]
            add_face(
                [(x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height)],
                index,
            )

            neighbors = (
                (-1, 0, [(x0, y1), (x1, y1)]),
                (1, 0, [(x1, y0), (x0, y0)]),
                (0, -1, [(x0, y0), (x0, y1)]),
                (0, 1, [(x1, y1), (x1, y0)]),
            )
            for delta_row, delta_column, edge in neighbors:
                neighbor_height = height_at(row + delta_row, column + delta_column)
                if neighbor_height >= height:
                    continue
                (ax, ay), (bx, by) = edge
                add_face(
                    [
                        (ax, ay, neighbor_height),
                        (bx, by, neighbor_height),
                        (bx, by, height),
                        (ax, ay, height),
                    ],
                    index,
                )

    mesh = bpy.data.meshes.new("arctic-age-transition-relief")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    relief = bpy.data.objects.new("arctic-age-transition-relief", mesh)
    bpy.context.collection.objects.link(relief)
    relief.rotation_euler[2] = math.radians(-10)

    for pair in material_order:
        relief.data.materials.append(
            material(f"age-transition-{pair[0]}-{pair[1]}", mixed_color(pair))
        )
    for polygon, index in zip(relief.data.polygons, face_materials):
        polygon.material_index = index
        polygon.use_smooth = False
    return relief


def smooth_heights(values: np.ndarray, passes: int = 3) -> np.ndarray:
    """Apply a small separable blur without adding new observations."""
    result = values.astype(np.float32, copy=True)
    for _ in range(passes):
        padded_x = np.pad(result, ((0, 0), (1, 1)), mode="edge")
        result = (
            padded_x[:, :-2] + 2.0 * padded_x[:, 1:-1] + padded_x[:, 2:]
        ) / 4.0
        padded_y = np.pad(result, ((1, 1), (0, 0)), mode="edge")
        result = (
            padded_y[:-2, :] + 2.0 * padded_y[1:-1, :] + padded_y[2:, :]
        ) / 4.0
    return result


def create_smooth_relief(classes: np.ndarray) -> bpy.types.Object:
    rows, columns = classes.shape
    scale = 13.0 / max(rows, columns)
    radius = min(rows, columns) * 0.485
    center_row = (rows - 1) / 2
    center_column = (columns - 1) / 2
    material_order = (20, 1, 2, 3, 4, 5)
    material_index = {value: index for index, value in enumerate(material_order)}

    row_axis, column_axis = np.ogrid[:rows, :columns]
    inside_disc = np.hypot(row_axis - center_row, column_axis - center_column) <= radius
    visible = inside_disc & np.isin(classes, material_order)
    cell_heights = np.zeros((rows, columns), dtype=np.float32)
    for value, height in HEIGHTS.items():
        cell_heights[classes == value] = height
    cell_heights = smooth_heights(cell_heights)

    corner_heights = np.zeros((rows + 1, columns + 1), dtype=np.float32)
    corner_weights = np.zeros_like(corner_heights)
    for row_offset in (0, 1):
        for column_offset in (0, 1):
            corner_heights[
                row_offset : row_offset + rows,
                column_offset : column_offset + columns,
            ] += cell_heights
            corner_weights[
                row_offset : row_offset + rows,
                column_offset : column_offset + columns,
            ] += 1.0
    corner_heights /= np.maximum(corner_weights, 1.0)

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    face_materials: list[int] = []
    vertex_lookup: dict[tuple[int, int], int] = {}

    def vertex_index(row: int, column: int) -> int:
        key = (row, column)
        if key not in vertex_lookup:
            x = (column - center_column - 0.5) * scale
            y = (center_row - row + 0.5) * scale
            vertex_lookup[key] = len(vertices)
            vertices.append((x, y, float(corner_heights[row, column])))
        return vertex_lookup[key]

    for row in range(rows):
        for column in range(columns):
            if not visible[row, column]:
                continue
            faces.append(
                (
                    vertex_index(row + 1, column),
                    vertex_index(row + 1, column + 1),
                    vertex_index(row, column + 1),
                    vertex_index(row, column),
                )
            )
            face_materials.append(material_index[int(classes[row, column])])

    mesh = bpy.data.meshes.new("arctic-age-smooth-relief")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    relief = bpy.data.objects.new("arctic-age-smooth-relief", mesh)
    bpy.context.collection.objects.link(relief)
    relief.rotation_euler[2] = math.radians(-10)

    for value in material_order:
        name = "land" if value == 20 else f"age-{value}"
        relief.data.materials.append(material(name, COLORS[value]))
    for polygon, index in zip(relief.data.polygons, face_materials):
        polygon.material_index = index
        polygon.use_smooth = True

    subdivision = relief.modifiers.new("gentle-surface", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 1
    subdivision.render_levels = 1
    return relief


def create_disc() -> None:
    ocean = material("ocean", (0.003, 0.018, 0.028, 1.0))
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=256,
        radius=6.32,
        depth=0.08,
        location=(0, 0, -0.055),
    )
    disc = bpy.context.object
    disc.name = "polar-ocean-disc"
    disc.data.materials.append(ocean)

    grid = material("polar-grid", (0.015, 0.11, 0.14, 1.0))
    grid.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.15
    for radius in (2.0, 4.0, 6.0):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=radius,
            minor_radius=0.008,
            major_segments=192,
            minor_segments=6,
            location=(0, 0, -0.008),
        )
        bpy.context.object.data.materials.append(grid)


def look_at(camera: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(
    name: str,
    location: tuple[float, float, float],
    energy: float,
    color: tuple[float, float, float],
    size: float,
) -> None:
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = energy
    light_data.color = color
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    bpy.context.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (0, 0, 0)
    look_at(light, (0, 0, 0))


def setup_scene(
    style: str,
    classes: np.ndarray,
    *,
    year: int,
    output: Path = OUTPUT,
    width: int = 1920,
    height: int = 1080,
    render_samples: int = 64,
    transition_to: np.ndarray | None = None,
    transition_amount: float = 0.0,
) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_blocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for data_block in list(data_blocks):
            if data_block.users == 0:
                data_blocks.remove(data_block)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = render_samples
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    suffix = {
        "block": "",
        "smooth": "-smooth",
        "transition": "-transition",
    }[style]
    scene.render.filepath = str(output / f"map-3d{suffix}-{year}.png")
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.world.color = BACKGROUND[:3]

    create_disc()
    if style == "smooth":
        create_smooth_relief(classes)
    elif style == "transition":
        if transition_to is None:
            raise ValueError("transition_to is required for transition style")
        create_transition_relief(classes, transition_to, transition_amount)
    else:
        create_block_relief(classes)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (0.9, -7.2, 18.0)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 11.1
    look_at(camera, (0.4, 0.1, 0.10))

    add_area_light("key", (-4.5, -5.0, 12.0), 1050, (0.77, 0.90, 1.0), 7.0)
    add_area_light("rim", (6.0, 4.0, 8.0), 850, (0.18, 0.62, 0.82), 6.0)
    add_area_light("fill", (-5.0, 5.0, 5.0), 420, (1.0, 0.58, 0.32), 5.0)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", choices=("block", "smooth"), default="block")
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def main() -> None:
    args = parse_arguments()
    classes = np.load(OUTPUT / f"{YEAR}-classes.npy")
    setup_scene(args.style, classes, year=YEAR)
    suffix = "" if args.style == "block" else "-smooth"
    bpy.ops.wm.save_as_mainfile(
        filepath=str(OUTPUT / f"design-v4{suffix}-mockup.blend")
    )
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"V4 render failed: {error}", file=sys.stderr)
        raise
