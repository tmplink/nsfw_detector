# config.py
import os
import rarfile
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)

def load_config_from_file():
    """从/tmp/config加载配置并智能记录日志"""
    config_path = '/tmp/config'
    config_values = {}
    loaded_config = {}
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            key, value = map(str.strip, line.split('=', 1))
                            # 将配置键转换为大写
                            key = key.upper()
                            
                            # 尝试转换为适当的类型
                            try:
                                # 首先尝试转换为float
                                if '.' in value:
                                    loaded_config[key] = float(value)
                                else:
                                    # 然后尝试转换为int
                                    loaded_config[key] = int(value)
                            except ValueError:
                                # 如果转换失败，保持为字符串
                                loaded_config[key] = value
                                
                            config_values[key] = loaded_config[key]
                        except ValueError:
                            logger.warning(f"无法解析配置行: {line}")
            
            # 记录加载的配置
            if loaded_config:
                logger.info("配置加载详情:")
                logger.info("-" * 50)
                for key, value in loaded_config.items():
                    logger.info(f"{key:25s} = {value:<15}")
            
        else:
            logger.warning(f"配置文件{config_path}不存在，使用默认配置")
    
    except Exception as e:
        logger.error(f"读取配置文件时出错: {str(e)}")
    
    return config_values

# 基础配置
rarfile.UNRAR_TOOL = "unrar"
rarfile.PATH_SEP = '/'
os.environ['HF_HOME'] = '/root/.cache/huggingface'

# MIME类型到文件扩展名的映射
# config.py 中的 MIME_TO_EXT 字典应该这样修改：

# MIME类型到文件扩展名的映射
MIME_TO_EXT = {
    # 图片格式
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/bmp': '.bmp',
    'image/tiff': '.tiff',
    'image/x-tiff': '.tiff',
    'image/x-tga': '.tga',
    'image/x-portable-pixmap': '.ppm',
    'image/x-portable-graymap': '.pgm',
    'image/x-portable-bitmap': '.pbm',
    'image/x-portable-anymap': '.pnm',
    'image/svg+xml': '.svg',
    'image/x-pcx': '.pcx',
    'image/vnd.adobe.photoshop': '.psd',
    'image/vnd.microsoft.icon': '.ico',
    'image/heif': '.heif',
    'image/heic': '.heic',
    'image/avif': '.avif',
    'image/jxl': '.jxl',
    
    # PDF格式
    'application/pdf': '.pdf',
    
    # 文档格式 (新增)
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    
    # 视频和容器格式
    'video/mp4': '.mp4',
    'video/x-msvideo': '.avi',
    'video/x-matroska': '.mkv',
    'video/quicktime': '.mov',
    'video/x-ms-wmv': '.wmv',
    'video/webm': '.webm',
    'video/MP2T': '.ts',    
    'video/x-flv': '.flv',
    'video/3gpp': '.3gp',
    'video/3gpp2': '.3g2',
    'video/x-m4v': '.m4v',
    'video/mxf': '.mxf',
    'video/x-ogm': '.ogm',
    'video/vnd.rn-realvideo': '.rv',
    'video/dv': '.dv',
    'video/x-ms-asf': '.asf',
    'video/x-f4v': '.f4v',
    'video/vnd.dlna.mpeg-tts': '.m2ts',
    'video/x-raw': '.yuv',
    'video/mpeg': '.mpg',
    'video/x-mpeg': '.mpeg',
    'video/divx': '.divx',
    'video/x-vob': '.vob',
    'video/x-m2v': '.m2v',
    
    # 压缩格式
    'application/x-rar-compressed': '.rar',
    'application/x-rar': '.rar',
    'application/vnd.rar': '.rar',
    'application/zip': '.zip',
    'application/x-7z-compressed': '.7z',
    'application/gzip': '.gz',
    'application/x-tar': '.tar',
    'application/x-bzip2': '.bz2',
    'application/x-xz': '.xz',
    'application/x-lzma': '.lzma',
    'application/x-zstd': '.zst',
    'application/vnd.ms-cab-compressed': '.cab'
}

# 文件扩展名集合
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tga', 
                   '.ppm', '.pgm', '.pbm', '.pnm', '.svg', '.pcx', '.psd', '.ico',
                   '.heif', '.heic', '.avif', '.jxl'}

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.webm', '.ts', '.flv',
                   '.3gp', '.3g2', '.m4v', '.mxf', '.ogm', '.rv', '.dv', '.asf',
                   '.f4v', '.m2ts', '.yuv', '.mpg', '.mpeg', '.divx', '.vob', '.m2v'}

ARCHIVE_EXTENSIONS = {'.7z', '.rar', '.zip', '.gz', '.tar', '.bz2', '.xz', 
                     '.lzma', '.zst', '.cab'}

# 添加新的文档扩展名集合
DOCUMENT_EXTENSIONS = {'.doc', '.docx'}

# 添加新的 MIME 类型集合
DOCUMENT_MIME_TYPES = {
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

# MIME 类型集合
IMAGE_MIME_TYPES = {mime for mime, ext in MIME_TO_EXT.items() if mime.startswith('image/')}
VIDEO_MIME_TYPES = {mime for mime, ext in MIME_TO_EXT.items() if mime.startswith('video/')}
ARCHIVE_MIME_TYPES = {mime for mime, ext in MIME_TO_EXT.items() if 
    mime.startswith('application/') and 
    any(keyword in mime for keyword in ['zip', 'rar', '7z', 'gzip', 'tar', 
        'bzip2', 'xz', 'lzma', 'zstd', 'cab'])}
PDF_MIME_TYPES = {'application/pdf'}

# 所有支持的 MIME 类型集合
SUPPORTED_MIME_TYPES = IMAGE_MIME_TYPES | VIDEO_MIME_TYPES | ARCHIVE_MIME_TYPES | PDF_MIME_TYPES | DOCUMENT_MIME_TYPES

# 默认配置值
MAX_FILE_SIZE = 20 * 1024 * 1024 * 1024  # 20GB
NSFW_THRESHOLD = 0.8
FFMPEG_MAX_FRAMES = 20
FFMPEG_TIMEOUT = 1800
CHECK_ALL_FILES = 0
MAX_INTERVAL_SECONDS = 30

# 从文件加载配置并更新全局变量
file_config = load_config_from_file()

# 更新全局变量
globals().update(file_config)

# 导出所有配置变量
__all__ = [
    'MIME_TO_EXT', 'IMAGE_EXTENSIONS', 'VIDEO_EXTENSIONS', 'ARCHIVE_EXTENSIONS',
    'DOCUMENT_EXTENSIONS',  # 新增
    'IMAGE_MIME_TYPES', 'VIDEO_MIME_TYPES', 'ARCHIVE_MIME_TYPES', 'PDF_MIME_TYPES',
    'DOCUMENT_MIME_TYPES',  # 新增
    'SUPPORTED_MIME_TYPES', 'MAX_FILE_SIZE', 'NSFW_THRESHOLD', 'FFMPEG_MAX_FRAMES', 
    'FFMPEG_TIMEOUT', 'CHECK_ALL_FILES', 'MAX_INTERVAL_SECONDS'
]