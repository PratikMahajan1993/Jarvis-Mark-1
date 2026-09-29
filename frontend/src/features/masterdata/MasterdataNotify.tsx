"use client";

import { useMasterdataChangedToast } from "@/components/masterdata/shared";

/** Invisible desk listener: toast when master data is created (Telegram / API). */
export function MasterdataNotify() {
  useMasterdataChangedToast();
  return null;
}
