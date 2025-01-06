service {
  name     = "backend"
  id       = "backend-local"
  address  = "127.0.0.1"
  port     = 8000
  checks = [
    {
      name     = "backend_http_check"
      http     = "http://127.0.0.1:8000/api/health"
      interval = "10s"
    }
  ]
}

