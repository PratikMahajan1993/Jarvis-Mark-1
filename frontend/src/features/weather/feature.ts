import { defineFeature } from "@/sdk";
import { WeatherCard } from "./WeatherCard";

defineFeature({
  id: "weather",
  title: "Weather",
  cards: [{ id: "weather-chip", slot: "monitor.rail", component: WeatherCard }],
});
