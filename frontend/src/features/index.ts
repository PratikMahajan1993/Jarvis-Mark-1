import "./weather/feature";
import "./masterdata/feature";
import { validateFeatureList } from "@/sdk/featureRegistry";

export const FEATURES = ["weather", "masterdata"] as const;

const check = validateFeatureList(FEATURES);
if (!check.ok) {
  if (process.env.NODE_ENV === "production") {
    console.error(`[features] ${check.error}`);
  } else {
    throw new Error(`[features] ${check.error}`);
  }
}
