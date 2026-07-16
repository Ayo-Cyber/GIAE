import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

// NOTE ON REFRESH: the access token is refreshed in the API proxy
// (app/api/v1/[...path]/route.ts), NOT here. NextAuth runs the jwt callback
// concurrently (session polling + every proxied request) and, in the App
// Router, re-writes the session cookie on its own endpoints — so refreshing
// inside this callback races and intermittently drops the stored refresh
// token. Keeping the callback a pure pass-through makes the cookie stable; the
// proxy reads it with getToken() and refreshes on demand.

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        try {
          const res = await fetch(`${process.env.API_URL}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });
          if (!res.ok) return null;
          const data = await res.json();
          return {
            id: data.user.id,
            email: data.user.email,
            firstName: data.user.firstName,
            lastName: data.user.lastName,
            accessToken: data.access_token,
            accessTokenExpires: Date.now() + data.expires_in * 1000,
            refreshToken: data.refresh_token,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  pages: {
    signIn: "/login",
    newUser: "/signup",
    error: "/login",
  },
  // Session lives as long as the refresh token (30 days). The access token
  // inside it is short-lived and transparently refreshed by the jwt callback.
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },
  callbacks: {
    // Pure pass-through: seed tokens on sign-in, otherwise return the token
    // unchanged. No mutation here → the session cookie is stable and the proxy
    // can rely on getToken() returning an intact refresh token.
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.firstName = user.firstName;
        token.lastName = user.lastName;
        token.accessToken = user.accessToken;
        token.accessTokenExpires = user.accessTokenExpires;
        token.refreshToken = (user as { refreshToken?: string }).refreshToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = token.id;
      session.user.firstName = token.firstName;
      session.user.lastName = token.lastName;
      session.accessToken = token.accessToken;
      session.accessTokenExpires = token.accessTokenExpires;
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};
