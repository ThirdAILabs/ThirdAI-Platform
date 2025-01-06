service {
  name    = "keycloak"
  id      = "keycloak-local"
  address = "127.0.0.1"
  port    = 8180
  checks = [
    {
      name     = "keycloak_http_check"
      http     = "http://127.0.0.1:8180"
      interval = "10s"
    }
  ]
}

