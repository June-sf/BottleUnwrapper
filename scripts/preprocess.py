import numpy as np
import trimesh
import argparse
import sys
import os
from scipy.ndimage import gaussian_filter1d

def align_robust(mesh):
    """
    通用对齐算法：兼容有底/无底、高瘦/矮胖模型。
    原理：旋转体的中心轴应与绝大多数侧面法线垂直。
    """
    # 1. 预处理：先移至重心
    mesh.vertices -= mesh.centroid

    # 2. 获取 PCA 的三个主方向作为候选轴
    pts = mesh.vertices
    try:
        u, s, vh = np.linalg.svd(pts, full_matrices=False)
        candidate_axes = vh
    except Exception:
        # 极少情况 SVD 失败，回退到单位阵
        candidate_axes = np.eye(3)

    # 3. 基于法线垂直度的评分机制
    # Score = sum(Area * |dot(Normal, Axis)|) -> 越小越好
    face_normals = mesh.face_normals
    face_areas = mesh.area_faces
    
    scores = []
    for i in range(3):
        axis = candidate_axes[i]
        dots = np.abs(np.dot(face_normals, axis))
        score = np.sum(face_areas * dots)
        scores.append(score)
    
    best_axis_idx = np.argmin(scores)
    principal_axis = candidate_axes[best_axis_idx]
    
    print(f"  [Auto-Align] Axis {best_axis_idx} score: {scores[best_axis_idx]:.2f} (lower is better)")

    # 4. 旋转对齐到 Z 轴
    target_axis = np.array([0, 0, 1])
    rotation_axis = np.cross(principal_axis, target_axis)
    norm = np.linalg.norm(rotation_axis)
    
    if norm > 1e-6:
        rotation_axis = rotation_axis / norm
        angle = np.arccos(np.clip(np.dot(principal_axis, target_axis), -1, 1))
        R = trimesh.transformations.rotation_matrix(angle, rotation_axis)
        mesh.apply_transform(R)
    
    # 5. XY 归零 (基于包围盒中心，确保半径计算准确)
    # Z 轴保持不动，或者也可以归零，这里选择保持相对 Z 结构
    center_xy = mesh.bounds.mean(axis=0)[:2]
    translation = [-center_xy[0], -center_xy[1], 0]
    mesh.apply_translation(translation)

    return mesh

def extract_stable_cylinder(mesh, output_path, bins=300, stability_tol=0.02):
    """
    基于半径稳定性提取瓶身。
    stability_tol: 半径变化率容忍度。0.02 表示相邻层半径变化超过 2% 即视为不稳定。
    """
    if len(mesh.vertices) == 0:
        sys.exit("Error: Empty mesh")

    z = mesh.vertices[:, 2]
    z_min, z_max = z.min(), z.max()
    height = z_max - z_min
    
    if height < 1e-6:
        sys.exit("Error: Flat mesh (no height)")

    # === Step 1: 计算半径曲线 ===
    # 计算每个顶点的 XY 半径
    radii_verts = np.linalg.norm(mesh.vertices[:, :2], axis=1)
    
    bin_edges = np.linspace(z_min, z_max, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_indices = np.digitize(z, bin_edges)
    
    profile_r = []
    for i in range(1, bins + 1):
        mask = bin_indices == i
        if np.any(mask):
            # 取该层 90% 分位的半径 (排除内部结构干扰)
            r_layer = np.percentile(radii_verts[mask], 90)
        else:
            # 空层插值处理
            r_layer = profile_r[-1] if len(profile_r) > 0 else 0
        profile_r.append(r_layer)
    
    profile_r = np.array(profile_r)
    
    # === Step 2: 平滑曲线与计算梯度 ===
    # 高斯平滑，消除网格本身的不平整噪点
    sigma = 2 
    profile_smooth = gaussian_filter1d(profile_r, sigma)
    
    # 计算变化梯度 (Gradient)
    # diff[i] = r[i+1] - r[i-1]
    # 归一化梯度：变化量 / 平均半径 (处理不同粗细的瓶子)
    mean_r = np.mean(profile_smooth)
    if mean_r < 1e-6: mean_r = 1.0
    
    gradient = np.gradient(profile_smooth)
    norm_gradient = np.abs(gradient) / mean_r

    # === Step 3: 寻找稳定段 ===
    # 判定标准：归一化梯度小于容忍度
    is_stable = norm_gradient < stability_tol
    
    # 寻找连续的 True 区域
    segments = []
    current_segment = []
    
    for i, stable in enumerate(is_stable):
        if stable:
            current_segment.append(i)
        else:
            if current_segment:
                segments.append(current_segment)
                current_segment = []
    if current_segment:
        segments.append(current_segment)
        
    if not segments:
        print("Warning: No stable cylinder detected! Adjust tolerance or check mesh.")
        # 回退策略：取整个中间 50%
        best_segment = range(int(bins*0.25), int(bins*0.75))
    else:
        # === Step 4: 评分选择最优段 ===
        # 评分公式：Score = Length * (Radius_Mean ^ 0.3)
        # 主要看长度，轻微倾向于更粗的段（防止选到极长的细吸管/瓶颈）
        best_score = -1
        best_segment = []
        
        print(f"Detected {len(segments)} stable segments:")
        
        for seg in segments:
            length = len(seg)
            # 过滤太短的噪点段 (小于总高度的 5%)
            if length < bins * 0.05:
                continue
                
            seg_r = np.mean(profile_smooth[seg])
            score = length * (seg_r ** 0.3)
            
            z_start = bin_centers[seg[0]]
            z_end = bin_centers[seg[-1]]
            print(f"  - Segment Z[{z_start:.2f}, {z_end:.2f}]: Len={length}, R={seg_r:.2f}, Score={score:.2f}")
            
            if score > best_score:
                best_score = score
                best_segment = seg
    
    if len(best_segment) == 0:
        sys.exit("Error: No valid body segment found.")

    # === Step 5: 切割并导出 ===
    # 稍微向内收缩一点点索引，避免边缘刚好卡在倒角上
    idx_start = best_segment[0] 
    idx_end = best_segment[-1]
    
    z_cut_min = bin_edges[idx_start]
    z_cut_max = bin_edges[idx_end + 1] # bin_edges 比 bins 多 1
    
    print(f"[Selection] Keeping Z range: [{z_cut_min:.3f}, {z_cut_max:.3f}]")
    
    # 筛选面
    v_mask = (z >= z_cut_min) & (z <= z_cut_max)
    f_mask = v_mask[mesh.faces].all(axis=1)
    
    valid_faces = np.where(f_mask)[0]
    
    if len(valid_faces) == 0:
        sys.exit("Error: Cut result is empty.")
        
    body_mesh = mesh.submesh([valid_faces], append=True)
    body_mesh.remove_unreferenced_vertices()
    
    body_mesh.export(output_path)
    print(f"[Saved] {output_path} (Faces: {len(body_mesh.faces)})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract stable cylinder body")
    parser.add_argument("--input", required=True, help="Input OBJ")
    parser.add_argument("--output", required=True, help="Output OBJ")
    # 容差：越小要求越直。0.02~0.05 是比较合理的范围
    parser.add_argument("--tol", type=float, default=0.03, help="Stability tolerance (gradient)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        sys.exit("Input file not found.")
        
    print(f"Processing: {args.input}")
    mesh = trimesh.load(args.input, force='mesh', process=False)
    
    # 1. 对齐
    mesh = align_robust(mesh)
    
    # 2. 提取
    extract_stable_cylinder(mesh, args.output, stability_tol=args.tol)