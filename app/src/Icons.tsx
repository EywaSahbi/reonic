// Thin line icons (Lucide-like, brand.md) for tap-card answers. Unknown options get no icon.
import type { ReactNode } from "react";

const S = (children: ReactNode) => (
  <svg viewBox="0 0 32 32" width="30" height="30" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {children}
  </svg>
);

const person = (x: number, key?: number) => (
  <g key={key}>
    <circle cx={x} cy={11} r={3.2} />
    <path d={`M${x - 5} 25v-3a5 5 0 0 1 10 0v3`} />
  </g>
);
const people = (n: number) => {
  const xs = n === 1 ? [16] : n === 2 ? [11, 21] : n === 3 ? [7, 16, 25] : [5, 12, 20, 27];
  return S(<>{xs.map((x, i) => person(x, i))}{n >= 5 && <path d="M27 5v6M24 8h6" />}</>);
};

const house = (w: number, x: number) => (
  <g>
    <path d={`M${x} 26V15l${w / 2} -7 ${w / 2} 7v11z`} />
    <path d={`M${x + w / 2 - 2} 26v-5h4v5`} />
  </g>
);

const car = (
  <>
    <path d="M5 21v-4l3-6h16l3 6v4z" />
    <path d="M5 21v3h3v-3M24 21v3h3v-3" />
    <circle cx="10" cy="17.5" r="1" /><circle cx="22" cy="17.5" r="1" />
  </>
);

const ICONS: Record<string, ReactNode> = {
  "1": people(1), "2": people(2), "3": people(3), "4": people(4), "5+": people(5),
  gas: S(<path d="M16 4c1 5 7 7 7 14a7 7 0 0 1-14 0c0-4 3-5 3-9 2 1 3 3 3 5 1-2 1-6 1-10z" />),
  oil: S(<path d="M16 4s8 9 8 15a8 8 0 0 1-16 0c0-6 8-15 8-15z" />),
  heatpump: S(<><rect x="4" y="7" width="24" height="18" rx="2" /><circle cx="13" cy="16" r="5" /><path d="M13 11v10M8 16h10" /><path d="M23 11v10" /></>),
  electric: S(<path d="M18 3 8 18h7l-2 11 11-16h-7z" />),
  district: S(<><path d="M4 27V12l8-4v19M12 27V5l8 4v18M20 27V14h8v13" /></>),
  other: S(<><circle cx="9" cy="16" r="1.5" /><circle cx="16" cy="16" r="1.5" /><circle cx="23" cy="16" r="1.5" /></>),
  "Yes, already": S(car),
  Planned: S(<>{car}<circle cx="25" cy="7" r="4.5" /><path d="M25 5v2.2l1.5 1" /></>),
  No: S(<>{car}<path d="M4 4l24 24" /></>),
  detached: S(house(22, 5)),
  semi: S(<>{house(13, 3)}{house(13, 16)}</>),
  terraced: S(<>{house(9, 2)}{house(9, 11.5)}{house(9, 21)}</>),
  "Yes, I have solar": S(<><path d="M4 22 9 10h18l-4 12z" /><path d="M7 16h18M14 10l-2 12M20 10l-2 12" /></>),
  "No solar yet": S(<><path d="M4 26V15l12-9 12 9v11z" /><circle cx="16" cy="18" r="3" /><path d="M16 12v1.5M16 22.5V24M10 18h1.5M20.5 18H22" /></>),
  gable: S(<path d="M3 24 16 9l13 15M7 24v4h18v-4" />),
  flat: S(<path d="M4 12h24v14H4zM4 16h24" />),
  mono: S(<path d="M4 18 28 9v17H4z" />),
};

export const iconFor = (option: string): ReactNode | null => ICONS[option] ?? null;
