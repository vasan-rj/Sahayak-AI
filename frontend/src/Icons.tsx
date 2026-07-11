/* Line icons — one visual language, currentColor, no emoji. Kept simple and
   legible at small and large sizes so they read as clear pictographs for users
   who navigate by picture, not text. */
import type { ReactNode } from "react";

type P = { className?: string };
const svg = (children: ReactNode) => ({ className }: P) => (
  <svg
    className={className}
    viewBox="0 0 24 24"
    width="1em"
    height="1em"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.9"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    {children}
  </svg>
);

export const IconMic = svg(
  <>
    <rect x="9" y="2.5" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
    <path d="M12 17.5V21M8.5 21h7" />
  </>,
);

export const IconSound = svg(
  <>
    <path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4Z" />
    <path d="M16.5 9a4 4 0 0 1 0 6" />
    <path d="M19 6.5a7.5 7.5 0 0 1 0 11" />
  </>,
);

export const IconDoc = svg(
  <>
    <path d="M6 2.5h8l4 4V21a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 21V2.5Z" />
    <path d="M14 2.5V6.5h4" />
    <path d="M9 12h6M9 15.5h6M9 8.5h2" />
  </>,
);

export const IconVoice = svg(
  <>
    <path d="M4 5.5h16a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H9l-4 3.5v-3.5H4a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1Z" />
    <path d="M8 9.5v2M12 8.5v4M16 9.5v2" />
  </>,
);

export const IconCheck = svg(<path d="M4.5 12.5 10 18 20 6.5" />);

export const IconPrint = svg(
  <>
    <path d="M6.5 8.5V3h11v5.5" />
    <path d="M6.5 17H4a1 1 0 0 1-1-1V10a1.5 1.5 0 0 1 1.5-1.5h15A1.5 1.5 0 0 1 21 10v6a1 1 0 0 1-1 1h-2.5" />
    <rect x="6.5" y="14" width="11" height="7" rx="1" />
  </>,
);

export const IconPlay = svg(<path d="M7 4.5v15l13-7.5-13-7.5Z" fill="currentColor" stroke="none" />);

export const IconWarn = svg(
  <>
    <path d="M12 3 22 20H2L12 3Z" />
    <path d="M12 9.5v5M12 17.5h.01" />
  </>,
);

// Brand mark: a document being confirmed — the whole product in one glyph.
export const IconMark = svg(
  <>
    <rect x="3.5" y="2.5" width="13" height="19" rx="2.5" />
    <path d="M7 7h6M7 10.5h6M7 14h3" />
    <circle cx="17" cy="16.5" r="4.5" fill="var(--paper)" />
    <path d="m15 16.5 1.5 1.5 3-3" />
  </>,
);
