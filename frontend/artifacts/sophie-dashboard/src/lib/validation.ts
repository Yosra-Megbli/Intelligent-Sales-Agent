const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Accepts +33 6 12 34 56 78, 0612345678, +32 476 12 34 56, etc.
// Deliberately loose (digits/spaces/+/-/() only, 6-20 chars) - phone
// formats vary too much across FR/BE/NL to validate more strictly
// client-side without rejecting valid numbers.
const PHONE_RE = /^[0-9+()\-.\s]{6,20}$/;

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}

export function isValidPhone(value: string): boolean {
  return PHONE_RE.test(value.trim());
}
