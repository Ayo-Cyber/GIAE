export { default } from "next-auth/middleware";

export const config = {
  matcher: ["/dashboard/:path*", "/jobs/:path*", "/database/:path*", "/keys/:path*", "/upgrade/:path*"],
};
