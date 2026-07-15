import type { NextConfig } from "next"

const apiUpstream =
  process.env.EGREGORE_API_UPSTREAM?.replace(/\/$/, "") ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8080" : "http://egregore-api:8080")

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/egregore/:path*",
        destination: `${apiUpstream}/:path*`,
      },
    ]
  },
  async redirects() {
    return [
      {
        source: "/investigations/:id",
        destination: "/work-orders/:id",
        permanent: true,
      },
    ]
  },
}

export default nextConfig
