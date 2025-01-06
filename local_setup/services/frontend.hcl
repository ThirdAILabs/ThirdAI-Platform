service {
  name    = "frontend"
  id      = "frontend-local"
  address = "127.0.0.1"
  port    = 3006
  checks = [
    {
      name     = "frontend_http_check"
      http     = "http://127.0.0.1:3006"
      interval = "10s"
    }
  ]
}

