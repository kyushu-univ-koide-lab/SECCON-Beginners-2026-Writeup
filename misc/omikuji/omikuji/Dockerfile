FROM python:3.14-alpine@sha256:5a824eb82cc75361f98611f3cfc5091ea33f10a6ccea4d4ebdabbc523b9a1614

RUN apk --no-cache add file socat
RUN adduser -D ctf

ADD main.py /home/ctf/omikuji/main.py
RUN chmod 500 /home/ctf/omikuji/main.py
RUN chown ctf:root /home/ctf -R

USER ctf
WORKDIR /home/ctf/omikuji/
CMD ["socat", "-T", "30", "TCP-L:33457,fork,reuseaddr,max-children=96", "EXEC:python3 -u main.py,stderr"]
