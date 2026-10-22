FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 HOME=/root BB_NODE=render
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg poppler-utils curl libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /root/bangla_bhai
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["./render_start.sh"]
