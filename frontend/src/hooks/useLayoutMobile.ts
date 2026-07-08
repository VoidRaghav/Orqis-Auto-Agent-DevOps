import { useEffect, useState } from "react";
import { isLayoutMobile, onLayoutMobileChange } from "@/lib/layout-breakpoint";

/** True when viewport ≤ 900px (landing layout / nav breakpoint). */
export function useLayoutMobile(): boolean {
  const [mobile, setMobile] = useState(isLayoutMobile);
  useEffect(() => onLayoutMobileChange(setMobile), []);
  return mobile;
}
