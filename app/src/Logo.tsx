// Sonnfeld logo mark (invented demo installer brand; sunset gradient from experience/brand.md).
export function SonnfeldMark() {
  return (
    <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden>
      <defs>
        <linearGradient id="sf-sun" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#f7a35c" /><stop offset="1" stopColor="#ee6a5b" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#sf-sun)" />
      <path d="M8 19a8 8 0 0 1 16 0" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M6 23h20" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M16 7v2.5M9.5 9.8l1.6 1.8M22.5 9.8l-1.6 1.8" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
