// Interface icons: 24×24 line icons drawn with the current text colour, so every platform renders
// them the same way (text glyphs such as ♡ or ⌕ vary by font). Always decorative: aria-hidden.
const P = {
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>',
  heart: '<path d="M12 20 4.7 12.9a4.4 4.4 0 0 1 6.2-6.3L12 7.7l1.1-1.1a4.4 4.4 0 0 1 6.2 6.3Z"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  left: '<path d="m15 6-6 6 6 6"/>',
  right: '<path d="m9 6 6 6-6 6"/>',
  grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r=".8"/><circle cx="4.5" cy="12" r=".8"/><circle cx="4.5" cy="18" r=".8"/>',
  filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
  external: '<path d="M7 17 17 7M9 7h8v8"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.6v.4"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  compare: '<path d="M7 7h13m-3-3 3 3-3 3M17 17H4m3-3-3 3 3 3"/>',
  quote: '<path d="M8 4h8M8 4a2 2 0 0 0-2 2v13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V6a2 2 0 0 0-2-2"/><path d="M9.5 10h5M9.5 14h5"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  download: '<path d="M12 4v11m-4.5-4.5L12 15l4.5-4.5M5 20h14"/>',
  print: '<path d="M7 9V4h10v5M7 17H5a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2"/><rect x="7" y="14" width="10" height="6" rx="1"/>',
  alert: '<path d="M12 4 2.8 19.5h18.4Z"/><path d="M12 10v4.5M12 17v.4"/>',
};

export function icon(name, cls = "") {
  return `<svg class="i${cls ? ` ${cls}` : ""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${P[name] || ""}</svg>`;
}
