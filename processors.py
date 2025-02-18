# processors.py
from transformers import pipeline
import subprocess
import numpy as np
from PIL import Image
import io
from docx import Document
import logging
import tempfile
import os
import shutil
import glob
from pdf2image import convert_from_path
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import ArchiveHandler, can_process_file, sort_files_by_priority
from config import (
    MAX_FILE_SIZE, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, 
    NSFW_THRESHOLD, FFMPEG_MAX_FRAMES, FFMPEG_TIMEOUT,ARCHIVE_EXTENSIONS
)

# 配置日志
logger = logging.getLogger(__name__)

# 初始化模型
pipe = pipeline("image-classification", model="Falconsai/nsfw_image_detection", device=-1)

class VideoProcessor:
    def __init__(self, video_path):
        self.video_path = video_path
        self.temp_dir = None
        self.duration = None
        self.frame_rate = None
        self.total_frames = None

    def _get_video_info(self):
        """获取视频基本信息"""
        try:
            # 使用 ffprobe 而不是 ffmpeg
            duration_cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-show_entries', 'stream=r_frame_rate',
                '-select_streams', 'v',
                '-of', 'json',
                self.video_path
            ]

            result = subprocess.run(
                duration_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=FFMPEG_TIMEOUT
            )

            if result.returncode != 0:
                raise Exception(f"Failed to get video info: {result.stderr.decode()}")

            # 解析视频信息
            import json
            info = json.loads(result.stdout.decode())
            
            # 获取时长
            if 'format' in info and 'duration' in info['format']:
                self.duration = float(info['format']['duration'])
            else:
                # 如果无法获取时长，使用替代命令
                alt_duration_cmd = [
                    'ffmpeg',
                    '-i', self.video_path,
                    '-f', 'null',
                    '-'
                ]
                result = subprocess.run(
                    alt_duration_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=FFMPEG_TIMEOUT
                )
                # 从stderr中解析时长信息
                duration_str = result.stderr.decode()
                import re
                duration_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}.\d{2})", duration_str)
                if duration_match:
                    hours, minutes, seconds = duration_match.groups()
                    self.duration = float(hours) * 3600 + float(minutes) * 60 + float(seconds)
                else:
                    self.duration = 0
            
            # 获取帧率
            if 'streams' in info and info['streams'] and 'r_frame_rate' in info['streams'][0]:
                fr_str = info['streams'][0]['r_frame_rate']
                if '/' in fr_str:
                    fr_num, fr_den = map(int, fr_str.split('/'))
                    self.frame_rate = fr_num / fr_den if fr_den != 0 else 0
                else:
                    self.frame_rate = float(fr_str)
            else:
                self.frame_rate = 25.0  # 默认帧率
            
            # 计算总帧数
            self.total_frames = int(self.duration * self.frame_rate) if self.duration and self.frame_rate else 0
            
            logger.info(f"视频信息: 时长={self.duration:.2f}秒, "
                       f"帧率={self.frame_rate:.2f}fps, "
                       f"总帧数={self.total_frames}")
                       
        except subprocess.TimeoutExpired:
            raise Exception("获取视频信息超时")
        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")

    def _extract_keyframes(self):
        """提取视频帧，使用固定帧率策略"""
        try:
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp()
            logger.info("开始提取视频帧...")
            
            if not self.duration:
                raise ValueError("视频信息不完整，请先调用 _get_video_info()")
                
            # 计算采样帧率，添加安全检查
            if self.duration < FFMPEG_MAX_FRAMES:
                # 如果视频时长小于预期提取的帧数，则每秒提取一帧
                fps = "1"
                frames_to_extract = min(int(self.duration), FFMPEG_MAX_FRAMES)
            else:
                # 正常情况下的帧率计算
                interval_seconds = max(1, int(self.duration / FFMPEG_MAX_FRAMES))
                fps = f"1/{interval_seconds}"
                frames_to_extract = FFMPEG_MAX_FRAMES
                
            logger.info(f"视频总长: {self.duration:.2f}秒, FPS: {fps}, 计划提取帧数: {frames_to_extract}")
            
            # 使用 fps filter 提取帧
            extract_cmd = [
                'ffmpeg',
                '-i', self.video_path,
                '-vf', f'fps={fps}',         # 使用固定帧率
                '-frame_pts', '1',           # 输出时间戳
                '-vframes', str(frames_to_extract),  # 限制提取帧数
                '-q:v', '2',                 # 高质量（1-31，1最好）
                '-y',                        # 覆盖已存在文件
                os.path.join(self.temp_dir, 'frame-%d.jpg')
            ]
                
            # 执行提取命令
            result = subprocess.run(
                extract_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=FFMPEG_TIMEOUT,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"提取帧失败，FFMPEG输出: {result.stderr}")
                
                # 如果第一次提取失败，尝试使用更保守的设置
                conservative_cmd = [
                    'ffmpeg',
                    '-i', self.video_path,
                    '-r', '1',               # 强制输出帧率为1fps
                    '-vframes', str(frames_to_extract),
                    '-q:v', '2',
                    '-y',
                    os.path.join(self.temp_dir, 'frame-%d.jpg')
                ]
                
                logger.info("尝试使用备选提取方法...")
                result = subprocess.run(
                    conservative_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=FFMPEG_TIMEOUT,
                    text=True
                )
                
                if result.returncode != 0:
                    raise Exception(f"提取帧失败（备选方法）: {result.stderr}")
            
            # 获取所有提取的帧文件并排序
            frames = sorted(glob.glob(os.path.join(self.temp_dir, 'frame-*.jpg')))
            extracted_count = len(frames)
            
            if extracted_count == 0:
                raise Exception("未能提取到任何帧")
            
            if extracted_count < frames_to_extract:
                logger.warning(f"实际提取帧数({extracted_count})小于计划帧数({frames_to_extract})")
            
            logger.info(f"成功提取 {extracted_count} 个帧")
            return frames
                
        except subprocess.TimeoutExpired:
            logger.error("提取帧操作超时")
            raise Exception(f"提取帧操作超时（超过 {FFMPEG_TIMEOUT} 秒）")
        except Exception as e:
            logger.error(f"提取帧失败: {str(e)}")
            raise
        finally:
            # 注意：这里不要清理临时目录，因为返回的帧路径还需要被使用
            # 清理工作应该在帧处理完成后进行
            pass
    
    def _process_frame(self, frame_path):
        """处理单个帧"""
        try:
            with Image.open(frame_path) as img:
                result = process_image(img)
                frame_num = int(Path(frame_path).stem.split('-')[1])
                return frame_num, result
        except Exception as e:
            logger.error(f"处理帧 {frame_path} 失败: {str(e)}")
            return None, None

    def process(self):
        """按顺序处理视频文件"""
        try:
            # 获取视频信息
            self._get_video_info()
            
            # 提取关键帧
            frame_files = self._extract_keyframes()
            if not frame_files:
                logger.warning("未能提取到任何关键帧")
                return None
            
            # 按顺序处理帧
            last_result = None
            for frame in sorted(frame_files):
                frame_num, result = self._process_frame(frame)
                if result is not None:
                    last_result = result
                    if result['nsfw'] > NSFW_THRESHOLD:
                        logger.info(f"在帧 {frame_num} 发现匹配内容")
                        return result
            
            return last_result
            
        except Exception as e:
            logger.error(f"处理视频失败: {str(e)}")
            raise
            
        finally:
            # 清理临时文件
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                    logger.info("清理临时文件完成")
                except Exception as e:
                    logger.error(f"清理临时文件失败: {str(e)}")

def process_image(image):
    """处理单张图片并返回检测结果"""
    try:
        logger.info("开始处理图片")
        result = pipe(image)
        nsfw_score = next((item['score'] for item in result if item['label'] == 'nsfw'), 0)
        normal_score = next((item['score'] for item in result if item['label'] == 'normal'), 1)
        logger.info(f"图片处理完成: NSFW={nsfw_score:.3f}, Normal={normal_score:.3f}")
        return {
            'nsfw': nsfw_score,
            'normal': normal_score
        }
    except Exception as e:
        logger.error(f"图片处理失败: {str(e)}")
        raise Exception(f"Image processing failed: {str(e)}")

def process_pdf_file(pdf_stream):
    """使用 pdf2image 处理 PDF 文件并检查内容"""
    try:
        logger.info("开始处理PDF文件")
        
        # 创建临时文件保存 PDF 内容
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf.write(pdf_stream)
            tmp_pdf_path = tmp_pdf.name

        try:
            # 使用 pdf2image 将 PDF 转换为图片
            from pdf2image import convert_from_path
            images = convert_from_path(
                tmp_pdf_path,
                dpi=200,  # 设置较低的DPI以提高性能
                fmt='jpeg',
                thread_count=2  # 使用多线程提高性能
            )
            
            logger.info(f"PDF共转换出 {len(images)} 页图片")
            
            last_result = None
            
            # 处理每一页转换出的图片
            for page_num, image in enumerate(images, 1):
                try:
                    logger.info(f"正在处理第 {page_num} 页")
                    result = process_image(image)
                    last_result = result
                    
                    if result['nsfw'] > NSFW_THRESHOLD:
                        logger.info(f"在第 {page_num} 页发现匹配内容")
                        return result
                        
                except Exception as e:
                    logger.error(f"处理PDF第 {page_num} 页时出错: {str(e)}")
                    continue
            
            logger.info("PDF处理完成")
            return last_result  # 返回最后一次处理结果
            
        finally:
            # 清理临时PDF文件
            try:
                os.unlink(tmp_pdf_path)
            except Exception as e:
                logger.error(f"清理临时PDF文件失败: {str(e)}")
                
    except Exception as e:
        logger.error(f"PDF处理失败: {str(e)}")
        raise Exception(f"PDF processing failed: {str(e)}")
    
def process_doc_file(file_content):
    """处理 .doc 文件"""
    try:
        # 创建临时文件来存储 .doc 内容
        with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        try:
            # 使用 antiword 将 .doc 转换为文本
            result = subprocess.run(
                ['antiword', '-i', '1', tmp_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )

            # 检查是否包含图片（使用 antiword 的图片提取模式）
            img_dir = tempfile.mkdtemp()
            subprocess.run(
                ['antiword', '-i', '2', '-o', img_dir, tmp_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )

            # 检查提取的图片
            last_result = None
            for img_file in os.listdir(img_dir):
                if img_file.endswith(('.png', '.jpg', '.jpeg')):
                    img_path = os.path.join(img_dir, img_file)
                    with Image.open(img_path) as img:
                        result = process_image(img)
                        last_result = result
                        if result['nsfw'] > NSFW_THRESHOLD:
                            return result

            return last_result

        finally:
            # 清理临时文件
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            if os.path.exists(img_dir):
                import shutil
                shutil.rmtree(img_dir)

    except Exception as e:
        logger.error(f"处理 DOC 文件失败: {str(e)}")
        raise Exception(f"DOC processing failed: {str(e)}")

def process_docx_file(file_content):
    """处理 .docx 文件"""
    try:
        # 创建临时文件来存储 .docx 内容
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        try:
            # 使用 python-docx 加载文档
            doc = Document(tmp_file_path)
            
            # 提取和处理所有图片
            last_result = None
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        image_data = rel.target_part.blob
                        img = Image.open(io.BytesIO(image_data))
                        result = process_image(img)
                        last_result = result
                        if result['nsfw'] > NSFW_THRESHOLD:
                            return result
                    except Exception as img_error:
                        logger.error(f"处理 DOCX 中的图片失败: {str(img_error)}")
                        continue

            return last_result

        finally:
            # 清理临时文件
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        logger.error(f"处理 DOCX 文件失败: {str(e)}")
        raise Exception(f"DOCX processing failed: {str(e)}")

def process_video_file(video_path):
    """处理视频文件的入口函数"""
    processor = VideoProcessor(video_path)
    return processor.process()

def process_archive(filepath, filename, depth=0, max_depth=100):
    """处理压缩文件，支持嵌套压缩包
    
    Args:
        filepath: 压缩文件路径
        filename: 原始文件名
        depth: 当前递归深度
        max_depth: 最大递归深度，防止过深的嵌套
    """
    temp_dir = None
    try:
        # 确保 filename 正确编码
        encoded_filename = filename  # 保存原始文件名
        if isinstance(filename, bytes):
            with ArchiveHandler(filepath) as temp_handler:
                encoded_filename = temp_handler.__encode_filename(filename)
                
        # 检查递归深度
        if depth > max_depth:
            logger.warning(f"达到最大递归深度 {max_depth}")
            return {
                'status': 'error',
                'message': f'Maximum archive nesting depth ({max_depth}) exceeded'
            }, 400

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        logger.info(f"处理压缩文件: {encoded_filename}, 深度: {depth}, 临时文件路径: {filepath}")
        
        # 检查文件大小
        file_size = os.path.getsize(filepath)
        if file_size > MAX_FILE_SIZE:
            return {
                'status': 'error',
                'message': 'File too large'
            }, 400

        with ArchiveHandler(filepath) as handler:
            # 获取文件列表
            files = handler.list_files()
            
            # 分离可直接处理的文件和嵌套压缩包
            processable_files = []
            nested_archives = []
            
            for f in files:
                # 确保文件名已正确编码
                if isinstance(f, bytes):
                    f = handler.__encode_filename(f)
                    
                ext = os.path.splitext(f)[1].lower()
                if ext in ARCHIVE_EXTENSIONS:
                    nested_archives.append(f)
                elif can_process_file(f):
                    processable_files.append(f)
            
            if not processable_files and not nested_archives:
                return {
                    'status': 'error',
                    'message': 'No processable files found in archive'
                }, 400

            # 先处理可直接处理的文件
            if processable_files:
                sorted_files = sort_files_by_priority(handler, processable_files)
                last_result = None
                matched_content = None
                
                for inner_filename in sorted_files:
                    try:
                        # 确保内部文件名已正确编码
                        if isinstance(inner_filename, bytes):
                            inner_filename = handler.__encode_filename(inner_filename)
                            
                        content = handler.extract_file(inner_filename)
                        ext = os.path.splitext(inner_filename)[1].lower()
                        
                        if ext in IMAGE_EXTENSIONS:
                            img = Image.open(io.BytesIO(content))
                            result = process_image(img)
                            last_result = {
                                'matched_file': inner_filename,
                                'result': result
                            }
                            
                            if result['nsfw'] > NSFW_THRESHOLD:
                                matched_content = last_result
                                break
                        
                        elif ext == '.pdf':
                            result = process_pdf_file(content)
                            if result:
                                last_result = {
                                    'matched_file': inner_filename,
                                    'result': result
                                }
                                if result['nsfw'] > NSFW_THRESHOLD:
                                    matched_content = last_result
                                    break
                        
                        elif ext in VIDEO_EXTENSIONS:
                            temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                            try:
                                with open(temp_video.name, 'wb') as f:
                                    f.write(content)
                                
                                result = process_video_file(temp_video.name)
                                if result:
                                    last_result = {
                                        'matched_file': inner_filename,
                                        'result': result
                                    }
                                    if result['nsfw'] > NSFW_THRESHOLD:
                                        matched_content = last_result
                                        break
                            finally:
                                if os.path.exists(temp_video.name):
                                    os.unlink(temp_video.name)
                                    
                    except Exception as e:
                        logger.error(f"处理文件 {inner_filename} 时出错: {str(e)}")
                        continue

                if matched_content:
                    logger.info(f"在压缩包 {encoded_filename} 中发现匹配内容: {matched_content['matched_file']}")
                    return {
                        'status': 'success',
                        'filename': encoded_filename,
                        'result': matched_content['result']
                    }

            # 处理嵌套的压缩包
            for nested_archive in nested_archives:
                try:
                    # 确保嵌套压缩包文件名已正确编码
                    if isinstance(nested_archive, bytes):
                        nested_archive = handler.__encode_filename(nested_archive)
                        
                    temp_nested = tempfile.NamedTemporaryFile(delete=False)
                    content = handler.extract_file(nested_archive)
                    
                    with open(temp_nested.name, 'wb') as f:
                        f.write(content)
                    
                    # 递归处理嵌套压缩包
                    nested_result = process_archive(
                        temp_nested.name,
                        nested_archive,
                        depth + 1,
                        max_depth
                    )
                    
                    # 如果找到匹配内容，直接返回
                    if isinstance(nested_result, tuple):
                        status_code = nested_result[1]
                        if status_code == 200:
                            return nested_result[0]
                    elif nested_result.get('status') == 'success':
                        return nested_result
                        
                except Exception as e:
                    logger.error(f"处理嵌套压缩包 {nested_archive} 时出错: {str(e)}")
                    continue
                finally:
                    if os.path.exists(temp_nested.name):
                        os.unlink(temp_nested.name)

            # 如果所有文件都处理完还没有返回，返回最后一个结果
            if last_result:
                logger.info(f"处理压缩包 {encoded_filename} 完成，最后处理的文件: {last_result['matched_file']}")
                return {
                    'status': 'success',
                    'filename': encoded_filename,
                    'result': last_result['result']
                }
            
            return {
                'status': 'error',
                'message': 'No files could be processed successfully'
            }, 400

    except Exception as e:
        logger.error(f"处理压缩包时出错: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }, 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"清理临时目录时出错: {str(e)}")