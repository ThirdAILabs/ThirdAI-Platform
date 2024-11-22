/**
 * Federated Logout API Route using NextAuth and Keycloak
 *
 * This API handle the logout process for user. Here are the steps:
 *
 * 1. **Retrieve Token**:
 *    - Use `getToken` from `next-auth/jwt` to get the JWT from request. In production, it
 *      just works with https, since it looks for secure cookies.
 *    - Make sure token is present, else send error "No session present".
 *
 * 2. **Prepare Logout Parameters**:
 *    - `logoutParams` function create the necessary params for Keycloak logout.
 *    - It get protocol and host from request headers, default to 'http' and 'localhost' if not.
 *    - These params include `id_token_hint` and `post_logout_redirect_uri`.
 *    - Note: Some function only work if protocol is 'http' due to secure cookie settings.
 *
 * 3. **Send Logout Request to Keycloak**:
 *    - `sendEndSessionEndpointToURL` send a POST request to Keycloak logout endpoint with params.
 *    - It set headers properly and handle redirect manually.
 *
 * 4. **Clear Authentication Cookies**:
 *    - `clearAuthCookies` remove all auth related cookies to end session on client side.
 *    - Cookies are cleared with path '/', expired date, httpOnly, secure based on environment, and sameSite 'lax'.
 *
 * 5. **Handle Keycloak Response**:
 *    - If Keycloak respond with 302, get the redirect URL from 'Location' header.
 *    - If redirect URL exist, send it back to client and clear cookies.
 *    - Else, send error "No redirect location provided by Keycloak."
 *    - If response is ok but not 302, send "Unexpected response from Keycloak logout endpoint."
 *
 * 6. **Error Handling**:
 *    - Catch any error during process, log it and send "Internal Server Error" to client.
 */

import { JWT, getToken } from 'next-auth/jwt';
import { NextRequest, NextResponse } from 'next/server';

function logoutParams(req: NextRequest, token: JWT): Record<string, string> {
  const protocol = req.headers.get('x-forwarded-proto') || 'http';
  const host = req.headers.get('x-forwarded-host') || req.headers.get('host') || 'localhost';
  const baseUrl = `${protocol}://${host}`;

  return {
    id_token_hint: token.idToken as string,
    post_logout_redirect_uri: baseUrl,
  };
}

function handleEmptyToken() {
  const response = { error: 'No session present' };
  const responseHeaders = { status: 400 };
  return NextResponse.json(response, responseHeaders);
}

async function sendEndSessionEndpointToURL(req: NextRequest, token: JWT) {
  const endSessionEndPoint = new URL(
    `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/logout`
  );

  const params: Record<string, string> = logoutParams(req, token);
  const endSessionParams = new URLSearchParams(params);

  const response = await fetch(endSessionEndPoint.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: endSessionParams.toString(),
    method: 'POST',
    cache: 'no-store',
    redirect: 'manual',
  });

  return response;
}

function clearAuthCookies(response: NextResponse) {
  const cookies = [
    '__Secure-next-auth.session-token',
    '__Secure-next-auth.session-token.0',
    '__Secure-next-auth.session-token.1',
    '__Host-next-auth.csrf-token',
    '__Secure-next-auth.callback-url',
  ];

  cookies.forEach((cookieName) => {
    response.cookies.set(cookieName, '', {
      path: '/',
      expires: new Date(0),
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
    });
  });
}

export async function GET(req: NextRequest) {
  try {
    console.log('Request: ', req);
    const token = await getToken({
      req,
      secret: process.env.NEXTAUTH_SECRET,
      secureCookie: process.env.NODE_ENV === 'production',
    });

    if (!token) {
      return handleEmptyToken();
    }

    const response = await sendEndSessionEndpointToURL(req, token);

    console.log('Response: ', response);
    if (response.status === 302) {
      const redirectUrl = response.headers.get('Location');

      console.log('Redirect URL: ', redirectUrl);
      if (redirectUrl) {
        const response = NextResponse.json({ redirectUrl }, { status: 200 });

        clearAuthCookies(response);

        return response;
      } else {
        return NextResponse.json(
          { error: 'No redirect location provided by Keycloak.' },
          { status: 500 }
        );
      }
    }

    return NextResponse.json(
      { error: 'Unexpected response from Keycloak logout endpoint.' },
      { status: response.status }
    );
  } catch (error) {
    console.error('Logout Error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
