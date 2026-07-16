import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface User {
    id: string;
    firstName?: string;
    lastName?: string;
    accessToken: string;
    accessTokenExpires: number;
    refreshToken?: string;
  }

  interface Session {
    accessToken: string;
    accessTokenExpires: number;
    error?: string;
    user: {
      id: string;
      email: string;
      firstName?: string;
      lastName?: string;
      name?: string | null;
      image?: string | null;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    firstName?: string;
    lastName?: string;
    accessToken: string;
    accessTokenExpires: number;
    refreshToken?: string;
    error?: string;
  }
}
