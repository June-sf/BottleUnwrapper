# Bottle Unwrapper System

瓶身展开系统 - 用于将3D瓶身模型自动展开为2D UV贴图的工具集。

## 项目概述

该系统实现了一个完整的3D瓶身模型展开流程，包括自动对齐、瓶身提取、接缝检测、UV展开和纹理重绘等功能。支持命令行和图形界面两种操作方式，适用于文物数字化、包装设计、3D打印等领域。

## 功能特性

- **自动对齐**：基于法线垂直度的智能对齐算法，兼容有底/无底、高瘦/矮胖等多种瓶型
- **瓶身提取**：基于半径稳定性分析，自动提取瓶身的稳定圆柱部分
- **接缝检测**：自动检测并提取瓶身的最佳展开接缝
- **UV展开**：利用Blender进行圆柱投影，实现高质量UV展开
- **纹理重绘**：将原始纹理映射到新的UV坐标系统
- **图形界面**：直观的拖拽式操作界面，支持实时进度显示

## 系统架构

```
BottleUnwrapperSystem/
├── input/                 # 示例输入数据（供用户测试）
├── output/                # 输出目录（运行生成，仓库中为空）
│   └── .gitkeep
├── scripts/
│   ├── preprocess.py      # 自动对齐与瓶身提取
│   ├── seam_extract.py    # 接缝提取算法
│   ├── seam2uv.py         # Blender 圆柱投影 UV 展开
│   └── uv_repack.py       # 纹理重绘与映射
├── main.py                # 命令行主入口
├── gui.py                 # 图形用户界面（PyQt5）
├── requirements.txt       # Python 依赖列表
├── README.md              # 项目说明文档
└── LICENSE
```

## 技术依赖

- **Python 3.7+**：核心开发语言
- **Blender 4.0+**：用于3D模型处理和UV展开
- **PyQt5**：图形用户界面框架
- **trimesh**：3D网格处理库
- **numpy**：数值计算库
- **scipy**：科学计算库
- 所有 Python 依赖已整理至 requirements.txt。

## 安装说明

### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 2. 安装Blender

从[Blender官网](https://www.blender.org/download/)下载并安装Blender 4.0或更高版本。

### 3. 配置Blender路径

在`main.py`文件中修改Blender可执行文件路径：

```python
# 请根据实际情况修改 Blender 可执行文件路径
# Windows 示例: r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
# Mac 示例: "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER_PATH = r"E:\Softwares\Blender\blender.exe"
```

## 使用方法

### 1. 图形界面方式（推荐）

启动图形界面：

```bash
python gui.py
```

操作步骤：
1. 将OBJ文件拖拽到界面中的拖拽区域，或点击浏览选择文件
2. 系统会自动寻找同名的纹理文件（支持jpg、png、jpeg格式）
3. 点击"Start Processing"按钮开始处理
4. 处理完成后，结果将在界面中预览

### 2. 命令行方式

基本用法：

```bash
python main.py input.obj --texture texture.jpg --outdir output
```

参数说明：
- `input.obj`：输入的3D瓶身模型文件
- `--texture`：可选参数，原始纹理图片
- `--outdir`：可选参数，输出目录（默认：output）

## 处理流程

1. **预处理** (`preprocess.py`)：
   - 自动对齐模型到Z轴
   - 基于半径稳定性分析提取瓶身部分

2. **接缝提取** (`seam_extract.py`)：
   - 检测瓶身表面的最佳展开接缝
   - 输出接缝坐标到文本文件

3. **UV展开** (`seam2uv.py`)：
   - 调用Blender执行圆柱投影
   - 沿接缝展开UV坐标
   - 输出带有新UV的OBJ文件和UV布局图

4. **纹理重绘** (`uv_repack.py`)：
   - 将原始纹理映射到新的UV坐标
   - 输出重绘后的纹理图片

## 配置选项

### preprocess.py 配置

- `--tol`：稳定性容忍度（默认：0.03）
  - 数值越小，要求瓶身越直
  - 建议范围：0.02~0.05

### main.py 配置

- `BLENDER_PATH`：Blender可执行文件路径
  - 请根据实际安装路径修改

## 常见问题

### 1. Blender未找到

请确保在`main.py`中正确配置了Blender路径。

### 2. 瓶身提取失败

- 检查模型是否为完整的3D模型
- 尝试调整`--tol`参数，增加稳定性容忍度
- 确保模型单位合理，避免过小或过大

### 3. UV展开效果不佳

- 检查瓶身提取结果是否正确
- 确保接缝检测算法正常工作
- 尝试调整Blender的UV展开参数

## 输出文件说明

处理完成后，`outout/`输出目录将包含以下文件：

- `xxx_preprocessed.obj`：预处理后的瓶身模型
- `xxx_seam.txt`：提取的接缝坐标
- `xxx_seamed.obj`：带有新UV的展开模型
- `xxx_uv.svg`：UV布局图
- `xxx_texture.png`：重绘后的纹理图片（如果提供了原始纹理）

## 应用场景

- **文物数字化**：将3D扫描的瓶状文物展开为2D图像，便于修复和研究
- **包装设计**：将3D瓶型展开为2D平面，用于包装设计和印刷
- **3D打印**：生成适合3D打印的展开模型
- **虚拟现实**：优化3D模型的纹理映射，提高渲染效率

## 技术支持

如需技术支持或有任何问题，请提交Issue。

## 许可证

本项目采用MIT许可证，详见LICENSE文件。
