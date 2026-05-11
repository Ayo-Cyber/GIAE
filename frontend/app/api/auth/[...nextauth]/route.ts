import NextAuth, { type NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

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
          // FastAPI returns { access_token, expires_in, user: { id, email, firstName, lastName } }
          return {
            id: data.user.id,
            email: data.user.email,
            firstName: data.user.firstName,
            lastName: data.user.lastName,
            accessToken: data.access_token,
            accessTokenExpires: Date.now() + data.expires_in * 1000,
          } as any;
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
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = (user as any).id;
        token.firstName = (user as { firstName?: string }).firstName;
        token.lastName = (user as { lastName?: string }).lastName;
        token.accessToken = (user as any).accessToken;
        token.accessTokenExpires = (user as any).accessTokenExpires;
      }
      return token;
    },
    async session({ session, token }) {
      if (token && session.user) {
        (session.user as { id?: string }).id = token.id as string;
        (session.user as { firstName?: string }).firstName = token.firstName as string;
        (session.user as { lastName?: string }).lastName = token.lastName as string;
        (session as any).accessToken = token.accessToken;
        (session as any).accessTokenExpires = token.accessTokenExpires;
      }
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
