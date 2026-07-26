import { z } from "zod";

export function parseApi<T>(schema: z.ZodType<T>, data: unknown, label = "API response"): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    console.warn(`${label} validation failed:`, result.error.flatten());
    throw new Error(`ข้อมูลจากเซิร์ฟเวอร์ไม่ถูกต้อง (${label})`);
  }
  return result.data;
}
