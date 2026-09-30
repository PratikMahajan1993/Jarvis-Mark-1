import { defineFeature } from "@/sdk";
import { SheetListenCard } from "./SheetListenCard";

defineFeature({
  id: "sheet-listen",
  title: "Shop logs",
  cards: [
    {
      id: "sheet-listen.monitor",
      slot: "monitor.rail",
      order: 30,
      size: "md",
      component: SheetListenCard,
    },
  ],
});
