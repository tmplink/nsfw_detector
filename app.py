# app.py
from flask import Flask, request, jsonify, send_file, Response, g
import tempfile
import os
import shutil
import logging
import magic
import gc
from pathlib import Path
from werkzeug.utils import secure_filename
from config import MAX_FILE_SIZE, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, MIME_TO_EXT, DOCUMENT_EXTENSIONS
from utils import ArchiveHandler, can_process_file, sort_files_by_priority
from processors import (
    process_image, process_pdf_file, process_video_file, 
    process_archive, process_doc_file, process_docx_file
)

# 配置日志
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 文件上传配置
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE  # 从config导入的最大文件大小
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()  # 使用系统临时目录
app.request_class.max_form_memory_size = 128 * 1024 * 1024  # 强制所有上传写入磁盘

# Load index.html content
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(CURRENT_DIR, 'index.html'), 'r', encoding='utf-8') as f:
    INDEX_HTML = f.read()

class TempFileHandler:
    """临时文件管理器"""
    def __init__(self):
        self.temp_files = []
        self.temp_dirs = []
        
    def create_temp_file(self, suffix=None):
        """创建临时文件"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        self.temp_files.append(temp_file.name)
        return temp_file
        
    def create_temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        return temp_dir
        
    def cleanup(self):
        """清理所有临时文件和目录"""
        # 清理文件
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"清理临时文件失败 {file_path}: {str(e)}")
        self.temp_files.clear()
        
        # 清理目录
        for dir_path in self.temp_dirs:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except Exception as e:
                logger.error(f"清理临时目录失败 {dir_path}: {str(e)}")
        self.temp_dirs.clear()
        
        # 强制垃圾回收
        gc.collect()

def detect_file_type(file_path):
    """检测文件类型，使用文件的前2048字节"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(2048)
        
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(header)
        
        # 对于RAR文件的特殊处理
        if mime_type not in MIME_TO_EXT:
            with open(file_path, 'rb') as f:
                if f.read(7).startswith(b'Rar!\x1a\x07'):
                    return 'application/x-rar', '.rar'
        
        return mime_type, MIME_TO_EXT.get(mime_type)
        
    except Exception as e:
        logger.error(f"文件类型检测失败: {str(e)}")
        raise

def process_file_by_type(file_path, detected_type, original_filename, temp_handler):
    """根据文件类型选择处理方法"""
    mime_type, ext = detected_type
    
    # 如果有原始文件扩展名，优先使用
    if original_filename and '.' in original_filename:
        original_ext = os.path.splitext(original_filename)[1].lower()
        if original_ext in IMAGE_EXTENSIONS or original_ext == '.pdf' or \
           original_ext in VIDEO_EXTENSIONS or original_ext in {'.rar', '.zip', '.7z', '.gz'} or \
           original_ext in DOCUMENT_EXTENSIONS:
            ext = original_ext
    
    if not ext:
        logger.error(f"不支持的文件类型: {mime_type}")
        return {
            'status': 'error',
            'message': f'Unsupported file type: {mime_type}'
        }, 400
    
    try:
        if ext in IMAGE_EXTENSIONS:
            with open(file_path, 'rb') as f:
                from PIL import Image
                # 使用with语句确保Image对象正确关闭
                with Image.open(f) as image:
                    result = process_image(image)
                    # 处理完图片后强制垃圾回收
                    gc.collect()
                    return {
                        'status': 'success',
                        'filename': original_filename,
                        'result': result
                    }
                
        elif ext == '.pdf':
            with open(file_path, 'rb') as f:
                pdf_stream = f.read()
                result = process_pdf_file(pdf_stream)
                # 处理完PDF后强制垃圾回收
                gc.collect()
                if result:
                    return {
                        'status': 'success',
                        'filename': original_filename,
                        'result': result
                    }
                return {
                    'status': 'error',
                    'message': 'No processable content found in PDF'
                }, 400
                
        elif ext in VIDEO_EXTENSIONS:
            result = process_video_file(file_path)
            # 处理完视频后强制垃圾回收
            gc.collect()
            if result:
                return {
                    'status': 'success',
                    'filename': original_filename,
                    'result': result
                }
            return {
                'status': 'error',
                'message': 'No processable content found in video'
            }, 400
                
        elif ext in {'.zip', '.rar', '.7z', '.gz'}:
            result = process_archive(file_path, original_filename)
            # 处理完压缩包后强制垃圾回收
            gc.collect()
            return result
            
        elif ext in DOCUMENT_EXTENSIONS:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                if ext == '.doc':
                    result = process_doc_file(file_content)
                else:  # .docx
                    result = process_docx_file(file_content)
                
                # 处理完文档后强制垃圾回收
                gc.collect()
                    
                if result:
                    return {
                        'status': 'success',
                        'filename': original_filename,
                        'result': result
                    }
                return {
                    'status': 'error',
                    'message': 'No processable content found in document'
                }, 400
            
        else:
            logger.error(f"不支持的文件扩展名: {ext}")
            return {
                'status': 'error',
                'message': f'Unsupported file extension: {ext}'
            }, 400
            
    except Exception as e:
        logger.error(f"处理文件时出错: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }, 500
    
@app.route('/')
def index():
    """Serve the index.html file"""
    return Response(INDEX_HTML, mimetype='text/html')

@app.route('/check', methods=['POST'])
def check_file():
    """统一的文件检查入口点"""
    temp_handler = TempFileHandler()
    try:
        # 获取请求中的 path 参数
        path = request.form.get('path')
        
        if path:
            # 处理文件路径
            abs_path = os.path.abspath(path)
            app_dir = os.path.abspath(os.path.dirname(__file__))
            
            # 安全检查：确保路径不指向程序目录
            if abs_path.startswith(app_dir):
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid path: cannot access program directory'
                }), 400
                
            # 检查文件是否存在
            if not os.path.exists(abs_path):
                return jsonify({
                    'status': 'error',
                    'message': 'File not found'
                }), 404
                
            # 检查是否是文件
            if not os.path.isfile(abs_path):
                return jsonify({
                    'status': 'error',
                    'message': 'Path is not a file'
                }), 400
                
            # 检查文件大小
            file_size = os.path.getsize(abs_path)
            if file_size > MAX_FILE_SIZE:
                return jsonify({
                    'status': 'error',
                    'message': 'File too large'
                }), 400
                
            # 获取原始文件名
            filename = os.path.basename(abs_path)
            
            # 检测文件类型
            detected_type = detect_file_type(abs_path)
            logger.info(f"检测到文件类型: {detected_type}")
            
            # 处理文件
            result = process_file_by_type(abs_path, detected_type, filename, temp_handler)
            return jsonify(result) if isinstance(result, dict) else jsonify(result[0]), result[1] if isinstance(result, tuple) else 200
            
        # 文件上传处理逻辑
        elif 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No file found'
            }), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No file selected'
            }), 400

        filename = secure_filename(file.filename)
        logger.info(f"接收到文件: {filename}")
        
        temp_file = temp_handler.create_temp_file()
        file.save(temp_file.name)
        
        file_size = os.path.getsize(temp_file.name)
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'status': 'error',
                'message': 'File too large'
            }), 400
        
        detected_type = detect_file_type(temp_file.name)
        logger.info(f"检测到文件类型: {detected_type}")
        
        result = process_file_by_type(temp_file.name, detected_type, filename, temp_handler)
        return jsonify(result) if isinstance(result, dict) else jsonify(result[0]), result[1] if isinstance(result, tuple) else 200

    except Exception as e:
        logger.error(f"处理过程发生错误: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        
    finally:
        # 清理所有临时文件
        temp_handler.cleanup()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3333)