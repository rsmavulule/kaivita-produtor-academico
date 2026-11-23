"use client";

import { useEffect } from "react";

/** A página privada não deve reaparecer a partir da cache do browser depois do logout. */
export function ReloadOnBack() {
  useEffect(() => {
    const onShow = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload();
    };
    window.addEventListener("pageshow", onShow);
    return () => window.removeEventListener("pageshow", onShow);
  }, []);
  return null;
}
