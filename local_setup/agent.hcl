bind_addr = "0.0.0.0"
data_dir  = "/opt/nomad/data"

client {
  enabled                     = true
}

server {
  enabled              = true
  bootstrap_expect = 1
}

plugin "docker" {
  config {
    volumes {
      enabled                = true
    }
  }
}

consul {
  address = "127.0.0.1:8500"  # Consul agent address
}

plugin "raw_exec" {
  config {
    enabled = true
  }
}

telemetry {
  collection_interval        = "1s"
  disable_hostname           = true
  prometheus_metrics         = true
  publish_allocation_metrics = true
  publish_node_metrics       = true
}

limits {
  http_max_conns_per_client = 0
  rpc_max_conns_per_client = 0
}