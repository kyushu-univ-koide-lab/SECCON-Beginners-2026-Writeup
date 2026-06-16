FROM python:3.14-alpine@sha256:5a824eb82cc75361f98611f3cfc5091ea33f10a6ccea4d4ebdabbc523b9a1614

RUN apk --no-cache add bash socat
RUN adduser -D ctf

WORKDIR /app
COPY main.py /app/main.py
RUN mkdir -p /app/bin \
    && chmod 500 /app/main.py \
    && chown ctf:root /app -R

USER ctf
CMD ["socat", "-T", "10", "TCP-L:46777,fork,reuseaddr,max-children=96", "EXEC:python3 -u main.py,stderr"]
