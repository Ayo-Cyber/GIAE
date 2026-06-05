import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface User {
    id: string;
    firstName?: string;
    lastName?: string;
    accessToken: string;
    accessTokenExpires: number;
  }

  interface Session {
    accessToken: string;
    accessTokenExpires: number;
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
  }
}
