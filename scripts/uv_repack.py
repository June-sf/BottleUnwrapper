import argparse
import numpy as np
from PIL import Image, ImageDraw
import scipy.ndimage

def load_obj_uv(obj_path):
    """
    快速读取 OBJ 的 UV 和面索引信息
    """
    uvs = []
    uv_faces = []
    
    # 预读取所有行以减少 IO 开销
    with open(obj_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        if line.startswith("vt "):
            parts = line.split()
            # 注意：这里保持 V 轴翻转，与原逻辑一致
            uvs.append([float(parts[1]), 1.0 - float(parts[2])])
        elif line.startswith("f "):
            parts = line.split()[1:]
            # 仅处理三角面或四边形（拆分为三角）
            # 这里简化处理，假设已经是三角面或取前三个点
            # 如果需要处理多边形，需增加三角化逻辑
            uv_indices = []
            for p in parts:
                vals = p.split('/')
                if len(vals) > 1 and vals[1]:
                    uv_indices.append(int(vals[1]) - 1)
            
            # 简单的三角剖分：(0, 1, 2), (0, 2, 3), ...
            for i in range(len(uv_indices) - 2):
                uv_faces.append([uv_indices[0], uv_indices[i+1], uv_indices[i+2]])
                
    return np.array(uvs), np.array(uv_faces)

def main():
    parser = argparse.ArgumentParser(description="Accelerated UV Repack using NumPy & SciPy")
    parser.add_argument("--old", required=True, help="Old OBJ path")
    parser.add_argument("--new", required=True, help="New OBJ path")
    parser.add_argument("--image", required=True, help="Original texture path")
    parser.add_argument("--out", required=True, help="Output texture path")
    parser.add_argument("--scale", type=float, default=1.0, help="Resolution scale")
    args = parser.parse_args()

    print("[1/5] Loading geometry...")
    old_uvs, old_faces = load_obj_uv(args.old)
    new_uvs, new_faces = load_obj_uv(args.new)

    # 确保面数量一致（如果不一致通常是因为 step2 导出时面序变了，或者有未展UV的面）
    if len(old_faces) != len(new_faces):
        print(f"Warning: Face count mismatch! Old: {len(old_faces)}, New: {len(new_faces)}")
        # 尝试截断较长的列表以继续运行（仅作容错）
        min_len = min(len(old_faces), len(new_faces))
        old_faces = old_faces[:min_len]
        new_faces = new_faces[:min_len]

    print("[2/5] Loading source image...")
    src_img = Image.open(args.image).convert("RGBA")
    src_w, src_h = src_img.size
    src_data = np.asarray(src_img).transpose(2, 0, 1) # (C, H, W) for scipy

    # 目标图像尺寸
    dst_w = int(src_w * args.scale)
    dst_h = int(src_h * args.scale)

    print(f"[3/5] Rasterizing face map ({dst_w}x{dst_h})...")
    # 使用 PIL 在内存中绘制“面索引图”
    # 模式 'I' (32-bit Integer) 支持大量面索引
    face_map_img = Image.new("I", (dst_w, dst_h), 0) # 0 表示背景
    draw = ImageDraw.Draw(face_map_img)

    # 准备绘制数据：将 UV 坐标 (0-1) 映射到 像素坐标
    # new_faces 是 (N, 3) 索引，new_uvs 是 (M, 2) 坐标
    # 获取所有面的三个顶点 UV 坐标
    tri_uvs = new_uvs[new_faces] * [dst_w, dst_h] # shape (N, 3, 2)
    
    # 批量绘制三角形
    # 由于 PIL 没有批量绘制接口，这里仍需循环，但仅循环面数(几万次)，而非像素数(几百万次)
    # 比纯 Python 像素判断快得多
    for i, tri in enumerate(tri_uvs):
        # 将浮点坐标转为元组列表 [(x1,y1), (x2,y2), (x3,y3)]
        poly = [tuple(p) for p in tri]
        # 填充颜色为索引值 + 1 (0留给背景)
        draw.polygon(poly, fill=i+1)

    # 转换为 NumPy 数组
    face_map = np.array(face_map_img)

    print("[4/5] Vectorized remapping...")
    # 获取所有非背景像素的坐标
    # mask: boolean array
    mask = face_map > 0
    # pixel_coords: (N_pixels, 2) -> (y, x)
    pixel_y, pixel_x = np.where(mask)
    
    # 获取这些像素对应的面索引 (减1还原为真实索引)
    face_indices = face_map[pixel_y, pixel_x] - 1
    
    # === 核心：向量化重心坐标计算 ===
    
    # 1. 获取对应像素所在三角形的新 UV 顶点 (A, B, C)
    # shape: (N_pixels, 2)
    # new_uvs[new_faces] shape is (F, 3, 2)
    # gather shape is (N_pixels, 3, 2)
    tris_new = new_uvs[new_faces[face_indices]] * [dst_w, dst_h]
    A = tris_new[:, 0, :]
    B = tris_new[:, 1, :]
    C = tris_new[:, 2, :]
    
    # 像素坐标 P (x, y)
    P = np.stack([pixel_x, pixel_y], axis=1).astype(float)
    
    # 计算重心坐标 (u, v, w)
    # 向量法: P = uA + vB + wC
    # 重心坐标公式 (利用叉乘/行列式面积比)
    v0 = B - A
    v1 = C - A
    v2 = P - A
    
    d00 = (v0 * v0).sum(axis=1)
    d01 = (v0 * v1).sum(axis=1)
    d11 = (v1 * v1).sum(axis=1)
    d20 = (v2 * v0).sum(axis=1)
    d21 = (v2 * v1).sum(axis=1)
    
    denom = d00 * d11 - d01 * d01
    # 避免除以零 (极少数退化三角形)
    denom[np.abs(denom) < 1e-8] = 1e-8
    
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    
    # Stack weights: (N_pixels, 3, 1) for broadcasting
    weights = np.stack([u, v, w], axis=1)[:, :, np.newaxis]
    
    # 2. 获取对应的旧 UV 顶点
    # old_uvs[old_faces] shape: (F, 3, 2)
    # gather shape: (N_pixels, 3, 2)
    tris_old = old_uvs[old_faces[face_indices]]
    
    # 3. 插值计算采样点 UV (Target Old UV)
    # target_uv = u*A_old + v*B_old + w*C_old
    # shape: (N_pixels, 2)
    target_uv = (weights * tris_old).sum(axis=1)
    
    # 映射到源图像素坐标
    sample_x = target_uv[:, 0] * src_w
    sample_y = target_uv[:, 1] * src_h
    
    # 4. 从源图采样颜色 (Bilinear Interpolation)
    # scipy map_coordinates 需要坐标格式为 (row_coords, col_coords) 即 (y, x)
    sample_coords = np.stack([sample_y, sample_x])
    
    # 结果容器
    out_pixels = np.zeros((4, len(pixel_x)), dtype=np.uint8)
    
    # 对 RGBA 4个通道分别进行采样 (order=1 为双线性插值, order=0 为最近邻)
    # 使用 mode='nearest' 处理边界，防止黑边
    for c in range(4):
        out_pixels[c] = scipy.ndimage.map_coordinates(
            src_data[c], sample_coords, order=1, mode='nearest', prefilter=False
        )
    
    print("[5/5] Saving result...")
    # 构建最终图像
    dst_img_arr = np.zeros((dst_h, dst_w, 4), dtype=np.uint8)
    # 将采样到的像素填回对应位置
    # out_pixels shape (4, N) -> transpose to (N, 4)
    dst_img_arr[pixel_y, pixel_x] = out_pixels.T
    
    final_img = Image.fromarray(dst_img_arr, "RGBA")
    final_img.save(args.out)
    print(f"Success! Saved to {args.out}")

if __name__ == "__main__":
    main()