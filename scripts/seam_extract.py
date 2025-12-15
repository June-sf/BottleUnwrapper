import trimesh
import networkx as nx
import numpy as np
import argparse

def extract_seam(input_obj, output_txt):
    print(f"[Step 1] Loading cleaned mesh: {input_obj}")
    mesh = trimesh.load(input_obj, process=False)
    
    # 1. 识别边界边 (只属于一个面的边)
    # group_rows 找出在 edges_sorted 中只出现一次的边
    edges = mesh.edges_sorted
    unique_edges = mesh.edges[trimesh.grouping.group_rows(edges, require_count=1)]
    
    # 获取边界上的所有顶点索引
    boundary_indices = np.unique(unique_edges.flatten())
    
    if len(boundary_indices) == 0:
        print("Error: Mesh is watertight (no boundaries). Cannot find top/bottom.")
        return

    # 2. 将边界顶点分为 Top 和 Bottom 两组
    # 通过 Z 坐标聚类 (K-Means 或简单的阈值，这里用简单的 Z 值排序分割)
    z_values = mesh.vertices[boundary_indices, 2]
    z_mean = np.mean(z_values)
    
    top_indices = boundary_indices[z_values > z_mean]
    bottom_indices = boundary_indices[z_values < z_mean]
    
    if len(top_indices) == 0 or len(bottom_indices) == 0:
        print("Error: Could not separate top and bottom loops.")
        return

    # 3. 确定起点和终点
    # 策略：选择 Top 环上 X 坐标最小的点，和 Bottom 环上几何距离最近的点
    # 这样生成的切缝比较直
    start_idx = top_indices[np.argmin(mesh.vertices[top_indices, 0])]
    
    # 在 bottom 中找最近点
    start_pos = mesh.vertices[start_idx]
    dists = np.linalg.norm(mesh.vertices[bottom_indices] - start_pos, axis=1)
    end_idx = bottom_indices[np.argmin(dists)]
    
    print(f"Seam Start (Top): {start_idx}, End (Bottom): {end_idx}")

    # 4. 图搜索最短路径 (Dijkstra)
    # trimesh.vertex_adjacency_graph 返回的是 NetworkX 图
    graph = mesh.vertex_adjacency_graph
    try:
        path = nx.shortest_path(graph, source=start_idx, target=end_idx)
    except nx.NetworkXNoPath:
        print("Error: No path found between top and bottom. Mesh might be disconnected.")
        return

    # 5. 导出 Seam
    print(f"Path found with {len(path)} vertices.")
    with open(output_txt, "w") as f:
        f.write("# index  x  y  z\n")
        for idx in path:
            v = mesh.vertices[idx]
            f.write(f"{idx} {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
    print(f"Saved seam to: {output_txt}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 1: Extract Seam")
    parser.add_argument("--input_obj", required=True)
    parser.add_argument("--output_txt", required=True)
    args = parser.parse_args()
    
    extract_seam(args.input_obj, args.output_txt)
