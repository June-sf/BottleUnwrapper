import bpy
import bmesh
import argparse
import sys
import os

def reset_blend():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def process_uv(args):
    print(f"[Step 2] Processing: {args.input_obj}")
    
    # 1. 导入
    # 兼容 Blender 4.x 和 3.x
    if hasattr(bpy.ops.wm, 'obj_import'):
        bpy.ops.wm.obj_import(filepath=args.input_obj)
    else:
        bpy.ops.import_scene.obj(filepath=args.input_obj)
        
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 2. 标记 Seam (可选，用于可视化切缝位置)
    # 虽然 Cylinder Projection 主要靠视角，但标记出来是个好习惯
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    
    # 读取 Seam 文件 (仅用于高亮显示，投影算法会自动切开背面)
    if os.path.exists(args.seam_txt):
        seam_indices = []
        with open(args.seam_txt, 'r') as f:
            for line in f:
                if not line.startswith('#'):
                    seam_indices.append(int(line.split()[0]))
        
        bpy.ops.mesh.select_all(action='DESELECT')
        # 简单连接逻辑用于标记
        for idx in seam_indices:
            if idx < len(bm.verts):
                bm.verts[idx].select = True
        # 选中点之间的边
        bpy.ops.mesh.select_mode(type='EDGE') 
        # 这里不进行复杂的路径连接，因为 Step 0 保证了拓扑简单
        
    # 3. 核心：圆柱投影 (Cylinder Projection)
    # 全选所有面
    bpy.ops.mesh.select_all(action='SELECT')
    
    # 使用圆柱投影，强制适配到 UV 边界
    # direction='VIEW_ON_EQUATOR': 假设模型直立
    # align='POLAR_ZX': 从 Z 轴看，X 轴为极轴，切缝通常在 -Y 方向
    # scale_to_bounds=True: 强制拉伸填满 0-1 空间 -> 严格矩形！
    bpy.ops.uv.cylinder_project(
        direction='VIEW_ON_EQUATOR',
        align='POLAR_ZX',
        pole='PINCH',
        scale_to_bounds=True
    )
    
    # 4. 导出
    # 导出 OBJ (含新 UV)
    if hasattr(bpy.ops.wm, 'obj_export'):
        bpy.ops.wm.obj_export(filepath=args.output_obj, export_uv=True)
    else:
        bpy.ops.export_scene.obj(filepath=args.output_obj, use_uvs=True)
        
    # 导出 Layout
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.uv.export_layout(
        filepath=args.output_layout,
        size=(2048, 2048),
        opacity=0.0,
        mode='SVG'
    )
    print("Done.")

if __name__ == "__main__":
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_obj", required=True)
    parser.add_argument("--seam_txt", required=True)
    parser.add_argument("--output_obj", required=True)
    parser.add_argument("--output_layout", required=True)
    
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        sys.exit(1)
        
    reset_blend()
    process_uv(args)
