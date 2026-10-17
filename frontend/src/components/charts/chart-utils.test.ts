import { describe, expect, it } from "vitest";
import { divergingColor, formatPValue, linearScale, niceDomain, niceTicks } from "./chart-utils";

describe("chart utilities", () => {
  it("builds round ticks and domains that contain the data", () => {
    expect(niceTicks(0, 100, 5)).toEqual([0, 25, 50, 75, 100]);
    expect(niceTicks(0.13, 0.91, 5)).toEqual([0.2, 0.4, 0.6, 0.8]);
    const [low, high] = niceDomain(812.4, 1187.2);
    expect(low).toBeLessThanOrEqual(812.4);
    expect(high).toBeGreaterThanOrEqual(1187.2);
    expect(niceDomain(5, 5)).toEqual([4, 6]);
  });

  it("maps linear scales and formats p-values", () => {
    expect(linearScale([0, 10], [100, 0])(2.5)).toBe(75);
    expect(formatPValue(0.0004)).toBe("<0.001");
    expect(formatPValue(0.0213)).toBe("0.021");
    expect(formatPValue(null)).toBe("—");
  });

  it("uses a neutral gray midpoint and opposite poles", () => {
    expect(divergingColor(0)).toBe("rgb(240, 239, 236)");
    expect(divergingColor(1)).toBe("rgb(28, 92, 171)");
    expect(divergingColor(-1)).toBe("rgb(180, 50, 50)");
    expect(divergingColor(2)).toBe(divergingColor(1));
  });
});
