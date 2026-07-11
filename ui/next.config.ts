import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone",
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
