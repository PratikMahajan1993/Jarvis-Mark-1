import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  serverExternalPackages: ["@huggingface/transformers", "onnxruntime-node", "sharp"],
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    config.resolve.alias["sharp$"] = false;
    config.resolve.alias["onnxruntime-node$"] = false;
    return config;
  },
};

export default nextConfig;
