import sys
import os
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTextEdit, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent

# 导入 main.py 中的 pipeline 函数
import main as backend

class WorkerSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bottle Unwrapper Pro")
        self.resize(900, 600)
        self.setAcceptDrops(True) # 启用主窗口拖拽

        self.input_obj = None
        self.input_tex = None
        
        # UI Components
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 1. 拖拽区域 / 文件显示
        self.drop_label = QLabel("Drag & Drop OBJ file here\n(Or click to browse)")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f0f0f0;
                font-size: 16px;
                color: #555;
            }
            QLabel:hover { background-color: #e0e0e0; }
        """)
        self.drop_label.setFixedHeight(150)
        # 支持点击选择
        self.drop_label.mousePressEvent = self.browse_file
        layout.addWidget(self.drop_label)

        # 2. 信息显示
        info_layout = QHBoxLayout()
        self.lbl_obj = QLabel("OBJ: None")
        self.lbl_tex = QLabel("Texture: None")
        info_layout.addWidget(self.lbl_obj)
        info_layout.addWidget(self.lbl_tex)
        layout.addLayout(info_layout)

        # 3. 运行按钮
        self.btn_run = QPushButton("Start Processing")
        self.btn_run.setFixedHeight(40)
        self.btn_run.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.start_processing)
        layout.addWidget(self.btn_run)

        # 4. 进度与日志
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # 5. 结果预览
        self.preview_label = QLabel("Result Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid #ddd; background: #fff;")
        self.preview_label.setMinimumHeight(200)
        layout.addWidget(self.preview_label, stretch=1)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext == ".obj":
                self.set_obj(f)
            elif ext in [".jpg", ".png", ".jpeg"]:
                self.set_tex(f)

    def browse_file(self, event):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open file', '.', "3D Files (*.obj)")
        if fname:
            self.set_obj(fname)

    def set_obj(self, path):
        self.input_obj = path
        self.lbl_obj.setText(f"OBJ: {os.path.basename(path)}")
        self.btn_run.setEnabled(True)
        self.drop_label.setText("OBJ Loaded.\n(Drag Texture here if needed)")
        
        # 自动寻找同名纹理
        base = os.path.splitext(path)[0]
        for ext in ['.jpg', '.png', '.jpeg']:
            if os.path.exists(base + ext):
                self.set_tex(base + ext)
                break

    def set_tex(self, path):
        self.input_tex = path
        self.lbl_tex.setText(f"Texture: {os.path.basename(path)}")

    def start_processing(self):
        if not self.input_obj:
            return
        
        # 锁定界面
        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0) # Infinite loading mode
        self.drop_label.setText("Processing...")
        
        # 后台运行
        self.signals = WorkerSignals()
        self.signals.finished.connect(self.on_finished)
        self.signals.error.connect(self.on_error)
        
        t = threading.Thread(target=self.run_pipeline_thread)
        t.start()

    def run_pipeline_thread(self):
        try:
            # 调用 main.py 中的 pipeline 函数
            output_path = backend.pipeline(self.input_obj, self.input_tex)
            self.signals.finished.emit(output_path)
        except Exception as e:
            self.signals.error.emit(str(e))

    def on_finished(self, result_path):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.btn_run.setEnabled(True)
        self.drop_label.setText("Success! Drag new files to restart.")
        
        # 显示图片
        if os.path.exists(result_path):
            pixmap = QPixmap(result_path)
            # 缩放以适应窗口
            scaled = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
        else:
            self.preview_label.setText("Processed, but no image generated.")

    def on_error(self, err_msg):
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        self.drop_label.setText("Error occurred.")
        QMessageBox.critical(self, "Processing Error", err_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())