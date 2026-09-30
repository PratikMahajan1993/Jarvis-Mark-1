export { Slot } from "./Slot";
export { defineSection } from "@/core/sections/defineSection";
export type { SectionDef, SectionProps, SlotId } from "@/core/sections/defineSection";
export {
  defineFeature,
  defineCard,
  getCardsForSlot,
  registeredFeatures,
  registeredSections,
  validateFeatureList,
} from "./featureRegistry";
export type { CardDef, FeatureDef } from "./featureRegistry";
export { FEATURE_SECTION_THEME, featureSectionOrb } from "./sectionPreset";
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
