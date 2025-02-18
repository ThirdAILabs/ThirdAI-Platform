import jwt
import os

# TODO(pratik): Replace these keys with Environment variables.
PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDgyAUl9RGfWdeX
hyo+ByzffCs7XaAf7+PDp3u9s6woYVe4wppauECkBy7+2i6/Iaqw95D+8mSHXDK7
akf8tDysNcfrsyzTaXl2ZS4k7XHMgCWdUs50r7eI///YT+Wbt3GQnPs23ZL+y6Kc
PGph+hletaXS3i7YfoSFA/N6tx+49wi1tmn83ZEnSUA778JDjc2XOfz3xHq2zLoK
HB05kKXVg/kuymktYU2MxyPTa4U+sHf7pxYqP26XnzCuv8Sl5bHdhaRsHCyfYxJ9
Uw13fmT9kYNaYDjNN2DvnVMAtKBkNX4Zm+nb2rfPbZZxe8ncuBvoqFJVwdQepbGQ
BSymxgCpAgMBAAECggEAAK9ShuSnbkQiiLKUdBfgjaXcU48z5EQ398IQTPoWigRB
tXCGjASQC6fkpa/7im3JwWw5rJf6t8f1209GAzmd2zT211hTO6nDoT/KhPm7ugCn
pkiieov8AktflIF2z/NrKBW2we2pWF3wturlgWFDxHkt27wwg2Yyrp1eCsRMapHF
pmWTtBNW1xiWQbmfJE5UASWYVQI5Q5rdpZLv2vXprtAA+uSE4JFtvezqkW98yjso
QmkqQNUVOjmOZ2jKtgIO6kAh+et9vnFl79XVozW1jrM1hFOSFzr86sp3z/LmJdyC
R/QMLXrwFJrKFwo2IHZKDP2P+Y3lA+Y7E08m+EMH4QKBgQD2jx07O3TfGhcGes5B
aVEBK0yvKBlwFBxHENC2lqWBI4UsdLej5OUODAYqF6YnW8Azq6sAxKk7WdzwZWQY
nsKYqmb43ftaqP5suJGqf/yw/96dYf8aczSHKJHEYZZmMeTZO1iM+QMFE2eNXpW2
R3Klvxzzpso+JR/RmpysNQOWiQKBgQDpY25DvxQfNTHF94TX1qd0V6uwNNEvtxFv
v+j+2tuz3xwSow+i1/mXSc5ZeIS/yCWEfVbOFZIFVS1+GFLlThuZyAlioiNuRM17
1WUkupyjBgsVfXGKC5MvMP8NfoGwbGJ5hKQOa0S5w3dYr4kSbl8ebf2l4b6rGtSH
7KeTPayRIQKBgQDeeU5YBxMyyHjkSOVZUm1cT7S3C8jAP/UwDrU1PAOE3gcpkPuv
MDeakDDzxDkRpJFuTkVTwSAuxKw+Yk6KhJ50YLXfc3V9XaWNdpFBtpDNKWO2wRkN
xcws9Odqut+ZwQWNGiaRtZMK/nJetm0Cd7+0XRkDpYkxwA/Q8uDR5lgheQKBgQC9
9b4jyfy4wfU3KpWnkAFQAqOtke/JpHm+uTcNaFl2d9xDlxD8/EkcSGh6DkwORPu0
cMgciRYG3SNgBLBED2ULr/NjopCwCbQuXKwsTu97CUowPaASOgWcXYbbFuK8FBu6
yKk3Szvu7xfOyWEJ7WfiPqg7QhiM8BOYZpimkYZJwQKBgQDqZvWjXm/ls/jj7BE4
EeYsKGDYsiTnkwGZfpxTD3vMgh8QCM0h4Ouq2gph6Q3dGHOvBAZ8lrUoGJYivP1d
jvSxHiMtyZAoH4EhTVAjlkAavOQu7vYC0U3QIwHJXme4H7bsSq11i9mrMhOgbJrD
wsrLbFp5MB71vcT+xNKuEFWuyQ==
-----END PRIVATE KEY-----"""
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4MgFJfURn1nXl4cqPgcs
33wrO12gH+/jw6d7vbOsKGFXuMKaWrhApAcu/touvyGqsPeQ/vJkh1wyu2pH/LQ8
rDXH67Ms02l5dmUuJO1xzIAlnVLOdK+3iP//2E/lm7dxkJz7Nt2S/suinDxqYfoZ
XrWl0t4u2H6EhQPzercfuPcItbZp/N2RJ0lAO+/CQ43Nlzn898R6tsy6ChwdOZCl
1YP5LsppLWFNjMcj02uFPrB3+6cWKj9ul58wrr/EpeWx3YWkbBwsn2MSfVMNd35k
/ZGDWmA4zTdg751TALSgZDV+GZvp29q3z22WcXvJ3Lgb6KhSVcHUHqWxkAUspsYA
qQIDAQAB
-----END PUBLIC KEY-----"""


def sign_role_payload(payload: dict) -> str:
    """
    Sign the payload using RS256 and return a JWT.
    """
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


def verify_role_payload(token: str) -> dict:
    """
    Verify the JWT signature using the public key.
    Returns the decoded payload if valid.
    """
    return jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
