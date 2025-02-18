// cryptoUtils.ts
import { importSPKI, jwtVerify } from 'jose';

// The PUBLIC_KEY must exactly match the public key used by the backend.
const PUBLIC_KEY_PEM = `-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4MgFJfURn1nXl4cqPgcs
33wrO12gH+/jw6d7vbOsKGFXuMKaWrhApAcu/touvyGqsPeQ/vJkh1wyu2pH/LQ8
rDXH67Ms02l5dmUuJO1xzIAlnVLOdK+3iP//2E/lm7dxkJz7Nt2S/suinDxqYfoZ
XrWl0t4u2H6EhQPzercfuPcItbZp/N2RJ0lAO+/CQ43Nlzn898R6tsy6ChwdOZCl
1YP5LsppLWFNjMcj02uFPrB3+6cWKj9ul58wrr/EpeWx3YWkbBwsn2MSfVMNd35k
/ZGDWmA4zTdg751TALSgZDV+GZvp29q3z22WcXvJ3Lgb6KhSVcHUHqWxkAUspsYA
qQIDAQAB
-----END PUBLIC KEY-----`;

export async function verifyRoleSignature(expectedPayload: object, token: string): Promise<boolean> {
  try {
    const publicKey = await importSPKI(PUBLIC_KEY_PEM, 'RS256');

    const { payload } = await jwtVerify(token, publicKey, { algorithms: ['RS256'] });
    
    return JSON.stringify(payload) === JSON.stringify(expectedPayload);
  } catch (error) {
    console.error("JWT verification error:", error);
    return false;
  }
}
