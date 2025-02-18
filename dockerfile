FROM debian:stable-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# 添加 non-free 仓库
RUN echo "deb http://deb.debian.org/debian stable main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security stable-security main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian stable-updates main contrib non-free" >> /etc/apt/sources.list

# 更新包列表
RUN apt-get update

# 基础 Python 环境
RUN apt-get install -y python3
RUN apt-get install -y python3-pip
RUN apt-get install -y python3-venv

# 压缩工具
RUN apt-get install -y unrar
RUN apt-get install -y p7zip-full
RUN apt-get install -y p7zip-rar

# 系统工具
RUN apt-get install -y curl
RUN apt-get install -y poppler-utils
RUN apt-get install -y ffmpeg

# OpenCV 相关依赖
RUN apt-get install -y python3-opencv
RUN apt-get install -y libgl1-mesa-glx
RUN apt-get install -y libglib2.0-0
RUN apt-get install -y libsm6
RUN apt-get install -y libxext6
RUN apt-get install -y libxrender-dev

# Python magic 依赖
RUN apt-get install -y python3-magic
RUN apt-get install -y libmagic1

# 文档解析工具
RUN apt-get install -y antiword

# 创建并激活虚拟环境
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Python 包安装 - 每个包单独安装以便调试
RUN pip3 install --no-cache-dir opencv-python-headless
RUN pip3 install --no-cache-dir rarfile
RUN pip3 install --no-cache-dir py7zr
RUN pip3 install --no-cache-dir flask==2.0.1
RUN pip3 install --no-cache-dir werkzeug==2.0.3
RUN pip3 install --no-cache-dir Pillow
RUN pip3 install --no-cache-dir transformers
RUN pip3 install --no-cache-dir pdf2image
RUN pip3 install --no-cache-dir python-docx
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip3 install --no-cache-dir python-magic

# 预下载模型
RUN python3 -c "from transformers import pipeline; pipe = pipeline('image-classification', model='Falconsai/nsfw_image_detection', device=-1)"

# 设置权限
RUN chmod -R 755 /root/.cache

# 源代码复制
COPY app.py config.py processors.py utils.py index.html /app/

CMD ["python3", "app.py"]