FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# 系统依赖安装放在最前面，因为这些很少改变
RUN apt-get update
RUN apt-get install -y python3
RUN apt-get install -y python3-pip
RUN apt-get install -y curl
RUN apt-get install -y unrar
RUN apt-get install -y p7zip-full
RUN apt-get install -y p7zip-rar
RUN apt-get install -y python3-opencv
RUN apt-get install -y libgl1-mesa-glx
RUN apt-get install -y libglib2.0-0
RUN apt-get install -y libsm6
RUN apt-get install -y libmagic1
RUN apt-get install -y libxext6
RUN apt-get install -y libxrender-dev
RUN apt-get install -y ffmpeg
RUN apt-get install -y poppler-utils

# 分解成多步执行 pip 安装
RUN pip3 install --no-cache-dir python-magic
RUN pip3 install --no-cache-dir opencv-python-headless
RUN pip3 install --no-cache-dir rarfile
RUN pip3 install --no-cache-dir py7zr
RUN pip3 install --no-cache-dir flask==2.0.1
RUN pip3 install --no-cache-dir werkzeug==2.0.3
RUN pip3 install --no-cache-dir Pillow
RUN pip3 install --no-cache-dir transformers
RUN pip3 install --no-cache-dir pdf2image
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 预下载模型
RUN python3 -c "from transformers import pipeline; pipe = pipeline('image-classification', model='Falconsai/nsfw_image_detection', device=-1)"

RUN chmod -R 755 /root/.cache

# 源代码复制放在最后，因为这些文件最容易变化
COPY app.py config.py processors.py utils.py index.html /app/

CMD ["python3", "app.py"]
