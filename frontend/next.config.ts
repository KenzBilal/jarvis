import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Tailwind v4 must be registered explicitly — without this rule the
  // `@import "tailwindcss"` in globals.css compiles to nothing (no preflight,
  // no utilities, no @theme tokens) and the app falls back to raw browser styles.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
