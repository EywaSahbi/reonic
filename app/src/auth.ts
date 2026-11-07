const KEY = "reo-installer-token";
let memoryToken = "";
export function getInstallerToken(): string {
  try { return sessionStorage.getItem(KEY) ?? memoryToken; } catch { return memoryToken; }
}
export function setInstallerToken(token: string): void {
  memoryToken = token.trim();
  try { if (memoryToken) sessionStorage.setItem(KEY, memoryToken); else sessionStorage.removeItem(KEY); } catch { /* memory lasts for this tab */ }
}
export function installerUnauthorized(): void {
  setInstallerToken("");
  window.dispatchEvent(new Event("reo-installer-unauthorized"));
}
export function isInstallerPath(path: string): boolean {
  return /^\/(plans|runs)(\/|\?|$)/.test(path) || path === "/calendar/slots" || path === "/prices";
}
