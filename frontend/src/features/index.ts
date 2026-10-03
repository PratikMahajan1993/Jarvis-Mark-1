import "./sheets/feature";
import "./weather/feature";
import "./masterdata/feature";
import "./sheet-listen/feature";
import { validateFeatureList } from "@/sdk/featureRegistry";

export const FEATURES = ["weather", "masterdata", "sheet-listen", "sheets"] as const;

const check = validateFeatureList(FEATURES);
if (!check.ok) {
  if (process.env.NODE_ENV === "production") {
    console.error(`[features] ${check.error}`);
  } else {
    throw new Error(`[features] ${check.error}`);
  }
}
