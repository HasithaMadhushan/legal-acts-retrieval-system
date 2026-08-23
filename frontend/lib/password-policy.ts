export const PASSWORD_HINT = "Use at least 8 characters with letters and numbers.";
export const PASSWORD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;

export function passwordMeetsPolicy(password: string) {
  return PASSWORD_PATTERN.test(password);
}
