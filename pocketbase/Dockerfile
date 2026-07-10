# PocketBase no publica imagen oficial: descargamos el binario de la release.
FROM alpine:3.20

ARG PB_VERSION=0.28.4

RUN apk add --no-cache unzip ca-certificates wget

RUN wget -q https://github.com/pocketbase/pocketbase/releases/download/v${PB_VERSION}/pocketbase_${PB_VERSION}_linux_amd64.zip -O /tmp/pb.zip \
    && unzip /tmp/pb.zip -d /pb/ \
    && rm /tmp/pb.zip

COPY entrypoint.sh /pb/entrypoint.sh
RUN chmod +x /pb/entrypoint.sh

EXPOSE 8090
WORKDIR /pb
ENTRYPOINT ["/pb/entrypoint.sh"]
