FROM python:3.11.5-alpine3.17

LABEL maintainer Daniel Hasselbach
COPY . .
RUN pip3 install -r requirements.txt

CMD python3 exporter.py