FROM python:3.12-slim

# cron 설치
RUN apt-get update && apt-get install -y cron tzdata && rm -rf /var/lib/apt/lists/*

# 타임존 설정 (한국 시간)
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 파일 복사
COPY . .

# .tmp 디렉토리 생성
RUN mkdir -p .tmp

# crontab 등록
COPY crontab /etc/cron.d/stock-report
RUN chmod 0644 /etc/cron.d/stock-report && crontab /etc/cron.d/stock-report

# 로그 파일 생성
RUN touch /var/log/cron.log

CMD ["cron", "-f"]
