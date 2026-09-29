import { defineFeature } from "@/sdk";
import { MasterdataNotify } from "./MasterdataNotify";

defineFeature({
  id: "masterdata",
  title: "Master data",
  cards: [{ id: "masterdata-notify", slot: "monitor.rail", component: MasterdataNotify }],
});
