export { Slot } from "./Slot";
export {
  defineFeature,
  defineCard,
  getCardsForSlot,
  registeredFeatures,
  validateFeatureList,
} from "./featureRegistry";
export type { CardDef, FeatureDef } from "./featureRegistry";
export { subscribeTopic } from "./events";
export { isFeatureEnabled, setFeatureFlag, setFeatureFlagDefault } from "./featureFlags";
export { api } from "@/lib/api";

export {
  useJarvisState,
  useJarvisSend,
  useSpeak,
  useSection,
  useOrb,
  useTaskQueue,
  requestApproval,
  useFeatureQuery,
  useFeatureMutation,
  useTopic,
  useActiveSession,
  useFeatureFlag,
  useToast,
  useDraft,
  useReducedMotion,
  useWeatherLine,
} from "./hooks";
