FROM python:3.11-alpine

RUN apk add --no-cache git

WORKDIR /.

RUN pip install --no-cache-dir --force-reinstall git+https://github.com/longnetwork/justbry.git

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "8000", "justbry.demo.morph:app"]
