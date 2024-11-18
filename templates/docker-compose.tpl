{{- $numServices := .Env.SERVICE_REPLICAS -}}
{{- $gpuByReplica := .Env.GPU_BY_REPLICA -}}
services:
  {{- range $i := seq 0 (sub $numServices 1) }}
  {{- $offset := (mul $i $gpuByReplica) -}}
  {{- $gpuSeq := seq $offset (add $offset (sub $gpuByReplica 1)) }}
  {{- $gpuList := join $gpuSeq "," }}
  {{- $gpuListQuoted := "" }}
  {{- range $index, $gpu := $gpuSeq }}
    {{- if eq $index 0 }}
      {{- $gpuListQuoted = printf "'%v'" $gpu }}
    {{- else }}
      {{- $gpuListQuoted = printf "%s,'%v'" $gpuListQuoted $gpu }}
    {{- end }}
  {{- end }}
  ollama-service-{{ add $i 1 }}:
    restart: always
    image: ollama/ollama
    tty: true
    expose:
      - "11434"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ollama-service.rule=Host(`${HOST}.nip.io`)"
      - "traefik.http.routers.ollama-service.entrypoints=websecure"
      - "traefik.http.routers.ollama-service.tls.certresolver=myresolver"
      - "traefik.http.middlewares.main-auth.basicauth.users=${CREDENTIALS}"
      - "traefik.http.routers.ollama-service.middlewares=main-auth@docker"
      - "traefik.http.services.ollama-service.loadbalancer.server.port=11434"
    environment:
      OLLAMA_KEEP_ALIVE: "-1"
    runtime: nvidia
    ipc: host
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: [{{ $gpuListQuoted }}]
              capabilities: [gpu]
    volumes:
      # - "./.ollama-service-{{ add $i 1 }}:/root/.ollama"
      - "./.ollama-service:/root/.ollama"
    networks:
      - ollama-network
  {{- end }}



  reverse-proxy:
    image: traefik:v3.2
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.web.http.redirections.entryPoint.to=websecure"
      - "--entrypoints.web.http.redirections.entryPoint.scheme=https"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.httpchallenge=true"
      - "--certificatesresolvers.myresolver.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.myresolver.acme.email=socialgroovybot@fabrique.social.gouv.fr"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./letsencrypt:/letsencrypt"
    networks:
      - ollama-network

networks:
  ollama-network:
    driver: bridge
