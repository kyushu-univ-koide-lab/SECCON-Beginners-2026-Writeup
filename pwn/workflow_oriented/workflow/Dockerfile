ARG CHALL_PLATFORM=linux/amd64
FROM --platform=${CHALL_PLATFORM} ubuntu:24.04 AS base

WORKDIR /app
COPY chall run
RUN echo "ctf4b{*** REDACTED ***}" > /flag.txt
RUN mkdir -p /app/docs
RUN echo "Workflow documents are stored here." > /app/docs/readme.txt

FROM pwn.red/jail
COPY --from=base / /srv
RUN chmod +x /srv/app/run
ENV JAIL_TIME=60 JAIL_CPU=100 JAIL_MEM=64M