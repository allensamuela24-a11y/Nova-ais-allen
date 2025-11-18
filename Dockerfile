FROM python:3.10-slim
RUN apt-get update && apt-get install -y build-essential git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
