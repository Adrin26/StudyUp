import { z } from "zod";

/** Mirrors backend `services/passwords.password_problems`; the server re-checks everything. */
export const newPassword = z
  .string()
  .min(8, "Use at least 8 characters.")
  .max(128, "Use at most 128 characters.")
  .refine((v) => /[a-zA-Z]/.test(v) && /\d/.test(v), "Include at least one letter and one number.");

export const confirmPasswords = <T extends { new_password: string; confirm: string }>(v: T) => v.new_password === v.confirm;
export const confirmMessage = { message: "Passwords do not match.", path: ["confirm"] };
