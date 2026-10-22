FROM python:3.13-slim

WORKDIR /app

COPY . ./

EXPOSE 3000

CMD ["python", "-m", "http.server", "3000", "--bind", "0.0.0.0", "--directory", "/app"]
