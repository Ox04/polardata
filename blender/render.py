"""Render Polar Memory height-map frames with Blender.

Run:
blender --background --python blender/render.py -- \
  --input data/processed/snapshots --output outputs/frames
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--samples", type=int, default=32)
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(values)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def make_grid(resolution: int, size: float = 10.0) -> bpy.types.Object:
    vertices = []
    faces = []
    half = size / 2
    for row in range(resolution):
        y = -half + size * row / (resolution - 1)
        for column in range(resolution):
            x = -half + size * column / (resolution - 1)
            vertices.append((x, y, 0.0))

    for row in range(resolution - 1):
        for column in range(resolution - 1):
            start = row * resolution + column
            faces.append(
                (
                    start,
                    start + 1,
                    start + resolution + 1,
                    start + resolution,
                )
            )

    mesh = bpy.data.meshes.new("memory-grid")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    surface = bpy.data.objects.new("memory-surface", mesh)
    bpy.context.collection.objects.link(surface)

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            row, column = divmod(vertex_index, resolution)
            uv_layer.data[loop_index].uv = (
                column / (resolution - 1),
                row / (resolution - 1),
            )
    return surface


def make_material() -> tuple[bpy.types.Material, bpy.types.ShaderNodeTexImage]:
    material = bpy.data.materials.new("sea-ice-age")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    principled.inputs["Roughness"].default_value = 0.72
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.interpolation = "Closest"
    links.new(image_node.outputs["Color"], principled.inputs["Base Color"])
    return material, image_node


def point_camera(camera: bpy.types.Object) -> None:
    direction = -camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_scene(samples: int) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.world.color = (0.004, 0.008, 0.015)
    scene.render.fps = 30
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 30
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_samples"):
        scene.eevee.taa_samples = samples

    bpy.ops.object.camera_add(location=(0.0, -9.6, 9.0))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 12.7
    point_camera(camera)
    scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=(-4.0, -4.0, 9.0))
    key = bpy.context.object
    key.data.energy = 1100
    key.data.shape = "DISK"
    key.data.size = 6.0

    bpy.ops.object.light_add(type="AREA", location=(5.0, 2.0, 5.0))
    fill = bpy.context.object
    fill.data.energy = 550
    fill.data.color = (0.52, 0.72, 1.0)
    fill.data.size = 5.0

    scene.render.image_settings.color_mode = "RGB"


def discover_frames(root: Path) -> list[tuple[Path, Path]]:
    pairs = []
    for height in sorted((root / "height").glob("*.png")):
        preview = root / "preview" / height.name
        if preview.is_file():
            pairs.append((height.resolve(), preview.resolve()))
    if not pairs:
        raise FileNotFoundError(f"height/preview 프레임 쌍을 찾지 못했습니다: {root}")
    return pairs


def render_frames(args: argparse.Namespace) -> None:
    clear_scene()
    configure_scene(args.samples)
    surface = make_grid(args.resolution)
    material, color_node = make_material()
    surface.data.materials.append(material)

    displacement_texture = bpy.data.textures.new("age-height", type="IMAGE")
    displacement_texture.extension = "CLIP"
    modifier = surface.modifiers.new("age-displacement", type="DISPLACE")
    modifier.texture = displacement_texture
    modifier.texture_coords = "UV"
    modifier.strength = 1.55
    modifier.mid_level = 0.0

    args.output.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    for index, (height_path, preview_path) in enumerate(
        discover_frames(args.input),
        start=1,
    ):
        height_image = bpy.data.images.load(str(height_path), check_existing=False)
        height_image.colorspace_settings.name = "Non-Color"
        color_image = bpy.data.images.load(str(preview_path), check_existing=False)
        displacement_texture.image = height_image
        color_node.image = color_image

        scene.frame_set(index)
        scene.render.filepath = str(args.output / f"frame-{index:04d}.png")
        bpy.ops.render.render(write_still=True)

        displacement_texture.image = None
        color_node.image = None
        bpy.data.images.remove(height_image)
        bpy.data.images.remove(color_image)


if __name__ == "__main__":
    render_frames(arguments())
