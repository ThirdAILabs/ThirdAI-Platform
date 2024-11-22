/**
 * NextAuth Configuration with Keycloak Provider
 *
 * This file setup the authentication options using NextAuth and Keycloak.
 *
 * **Providers**:
 * - **KeycloakProvider**: Configure Keycloak as the OAuth provider with client ID, secret, and issuer.
 *
 * **Session**:
 * - **Strategy**: Uses JWT for session management.
 * - **Max Age**: Session lasts for 30 minutes (60 * 30 seconds).
 *
 * **Callbacks**:
 * - **JWT Callback**:
 *   - If account is present, save idToken, accessToken, refreshToken, and expiresAt to token.
 *   - If token not expired, return it.
 *   - Else, try to refresh the access token using refreshToken.
 *   - Logs refreshed token, else set error in token.
 *   - Note: Refresh token only work if protocol is 'http' due to secure cookie.
 *
 * - **Session Callback**:
 *   - Attach accessToken, error, and expiresAt to session.
 *
 * **Logger**:
 * - Logs errors and warnings to console.
 *
 * **Debug**:
 * - Enabled to show debug information in development.
 *
 * **Secret**:
 * - Uses NEXTAUTH_SECRET from environment variables for signing tokens.
 */

import { access } from 'fs';
import { AuthOptions, TokenSet } from 'next-auth';
import { JWT } from 'next-auth/jwt';
import KeycloakProvider from 'next-auth/providers/keycloak';

function requestRefreshOfAccessToken(token: JWT) {
  return fetch(`${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/token`, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: process.env.KEYCLOAK_CLIENT_ID,
      client_secret: process.env.KEYCLOAK_CLIENT_SECRET,
      grant_type: 'refresh_token',
      refresh_token: token.refreshToken!,
    }),
    method: 'POST',
    cache: 'no-store',
  });
}

export const authOptions: AuthOptions = {
  providers: [
    KeycloakProvider({
      clientId: process.env.KEYCLOAK_CLIENT_ID,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET,
      issuer: process.env.KEYCLOAK_ISSUER,
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: '/auth/signin',
  },
  session: {
    strategy: 'jwt',
    maxAge: 60 * 30,
  },
  debug: true,
  logger: {
    error(code, ...message) {
      console.error('NextAuth error:', code, message);
    },
    warn(code, ...message) {
      console.warn('NextAuth warning:', code, message);
    },
  },
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        token.idToken = account.id_token;
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
        return token;
      }

      if (Date.now() < token.expiresAt! * 1000 - 60 * 1000) {
        return token;
      } else {
        try {
          const response = await requestRefreshOfAccessToken(token);
          const tokens: TokenSet = await response.json();

          if (!response.ok) throw tokens;

          const updatedToken: JWT = {
            ...token,
            idToken: tokens.id_token,
            accessToken: tokens.access_token,
            expiresAt: Math.floor(Date.now() / 1000 + (tokens.expires_in as number)),
            refreshToken: tokens.refresh_token ?? token.refreshToken,
          };
          console.log('Refreshed JWT token:', updatedToken);
          return updatedToken;
        } catch (error) {
          console.error('Error refreshing access token', error);
          return { ...token, error: 'RefreshAccessTokenError' };
        }
      }
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.error = token.error;
      session.expiresAt = token.expiresAt;
      return session;
    },
  },
};
