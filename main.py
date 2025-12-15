import os
import subprocess
import argparse
import sys
import shutil

# ================= 配置区域 =================
# 请根据实际情况修改 Blender 可执行文件路径
# Windows 示例: r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
# Mac 示例: "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER_PATH = r"E:\Softwares\Blender\blender.exe"
# ===========================================

def run_command(cmd, step_name):
    """执行 Shell 命令并打印日志"""
    print(f"\n[Step: {step_name}] Running...")
    try:
        # 使用 subprocess 调用外部脚本
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print(f"[Step: {step_name}] Success.")
        # print(result.stdout) # 正常情况下不打印详情
    except subprocess.CalledProcessError as e:
        print(f"[Step: {step_name}] Failed!")
        
        # === [新增] 打印标准输出 (包含你的 CRITICAL ERROR 信息) ===
        if e.stdout:
            print("--- STDOUT Log ---")
            print(e.stdout)
        
        # === 打印标准错误 (包含 Python 系统报错) ===
        if e.stderr:
            print("--- STDERR Log ---")
            print(e.stderr)
            
        raise RuntimeError(f"{step_name} failed.")

def pipeline(input_obj, input_texture, output_dir="output"):
    # 0. 准备路径
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 绝对路径化，防止 subprocess 调用时路径错乱
    input_obj = os.path.abspath(input_obj)
    if input_texture:
        input_texture = os.path.abspath(input_texture)
    output_dir = os.path.abspath(output_dir)
    
    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
    
    # 提取输入OBJ的文件名前缀（如"001.obj" -> "001"）
    base_name = os.path.splitext(os.path.basename(input_obj))[0]

    # 定义中间文件路径（基于前缀动态命名）
    path_v3_obj = os.path.join(output_dir, f"{base_name}_preprocessed.obj")  
    path_seam_txt = os.path.join(output_dir, f"{base_name}_seam.txt") 
    path_new_obj = os.path.join(output_dir, f"{base_name}_seamed.obj")  
    path_layout_svg = os.path.join(output_dir, f"{base_name}_uv.svg")  
    path_final_tex = os.path.join(output_dir, f"{base_name}_texture.png") 

    # === ① preprocess.py: 截取瓶身 ===
    cmd_1 = [
        sys.executable, os.path.join(scripts_dir, "preprocess.py"),
        "--input", input_obj,
        "--output", path_v3_obj,
        #"--threshold", "0.95" # 可根据需要调整阈值
    ]
    run_command(cmd_1, "Preprocess (Cut Body)")

    # === ② seam_extract.py: 提取接缝 ===
    cmd_2 = [
        sys.executable, os.path.join(scripts_dir, "seam_extract.py"),
        "--input_obj", path_v3_obj,
        "--output_txt", path_seam_txt
    ]
    run_command(cmd_2, "Seam Extraction")

    # === ③ seam2uv.py: Blender 圆柱投影 ===
    if not os.path.exists(BLENDER_PATH):
        raise FileNotFoundError(f"Blender executable not found at: {BLENDER_PATH}")
    
    # 注意：Blender 脚本调用格式为 blender -b -P script.py -- [args]
    cmd_3 = [
        BLENDER_PATH, "-b", "-P", os.path.join(scripts_dir, "seam2uv.py"),
        "--",
        "--input_obj", path_v3_obj,
        "--seam_txt", path_seam_txt,
        "--output_obj", path_new_obj,
        "--output_layout", path_layout_svg
    ]
    run_command(cmd_3, "UV Unwrapping (Blender)")

    # === ④ uv_repack.py: 纹理重绘 ===
    if input_texture and os.path.exists(input_texture):
        cmd_4 = [
            sys.executable, os.path.join(scripts_dir, "uv_repack.py"),
            "--old", path_v3_obj,
            "--new", path_new_obj,
            "--image", input_texture,
            "--out", path_final_tex,
            "--scale", "1.0"
        ]
        run_command(cmd_4, "Texture Repack")
    else:
        print("[Warning] No texture provided or file not found. Skipping repack.")

    print(f"\nAll Done! Results saved in: {output_dir}")
    return path_final_tex

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-Click Bottle Unwrapping Pipeline")
    parser.add_argument("input_obj", help="Path to the original OBJ file")
    parser.add_argument("--texture", help="Path to the original texture image (optional)", default=None)
    parser.add_argument("--outdir", help="Output directory", default="output")
    
    args = parser.parse_args()
    
    # 如果没有指定 texture，尝试在同目录下寻找同名图片
    if not args.texture:
        base_name = os.path.splitext(args.input_obj)[0]
        for ext in ['.jpg', '.png', '.jpeg']:
            if os.path.exists(base_name + ext):
                args.texture = base_name + ext
                print(f"Auto-detected texture: {args.texture}")
                break
    
    try:
        pipeline(args.input_obj, args.texture, args.outdir)
    except Exception as e:
        print(f"Pipeline Error: {e}")