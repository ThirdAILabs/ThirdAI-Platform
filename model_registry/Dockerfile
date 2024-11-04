FROM golang:1.23
WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY . .
RUN go build -v -o model_registry

ENV registry_db="data/registry.db"
ENV registry_storage="data/storage"
ENV registry_port="8080"

CMD ["./model_registry"]