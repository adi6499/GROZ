// Category illustrations from the approved V2 design reference. These are icons for categories and
// placeholders only -- they are never presented as photographs of a specific product.

const s = 'stroke-linecap="round" stroke-linejoin="round"';

const ART = {
  hammer: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-28 90 60)"><rect x="82" y="42" width="16" height="68" rx="7" fill="#f4511e"/><path d="M55 35Q55 27 64 27H119Q128 27 128 36V51Q128 59 119 59H64Q55 59 55 51Z" fill="#b9bec5" stroke="#737982" stroke-width="3"/><path d="M65 31H115" stroke="#fff" stroke-width="3"/></g></svg>`,
  sledge: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-37 90 60)"><rect x="82" y="34" width="16" height="80" rx="7" fill="#f4511e"/><rect x="45" y="19" width="90" height="31" rx="7" fill="#3d4148"/><rect x="51" y="22" width="78" height="5" rx="2" fill="#747982"/></g></svg>`,
  storage: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="translate(35 10)"><rect x="18" y="9" width="76" height="95" rx="5" fill="#27292e"/><rect x="24" y="16" width="64" height="13" rx="2" fill="#f4511e"/><rect x="24" y="34" width="64" height="13" rx="2" fill="#f4511e"/><rect x="24" y="52" width="64" height="13" rx="2" fill="#f4511e"/><rect x="24" y="70" width="64" height="13" rx="2" fill="#f4511e"/><circle cx="32" cy="108" r="6" fill="#454950"/><circle cx="81" cy="108" r="6" fill="#454950"/></g></svg>`,
  light: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-22 90 60)"><rect x="58" y="25" width="65" height="58" rx="9" fill="#30343a"/><rect x="66" y="33" width="49" height="42" rx="5" fill="#dce7ef"/><path d="M72 39L109 69M109 39L72 69" stroke="#fff" stroke-width="3"/><rect x="81" y="82" width="20" height="23" rx="5" fill="#f4511e"/></g></svg>`,
  measure: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-12 90 60)"><path d="M42 29H132V92H42Z" fill="#cfd4da" stroke="#6c727b" stroke-width="3"/><path d="M51 39V53M63 39V48M75 39V53M87 39V48M99 39V53M111 39V48M123 39V53" stroke="#4e535b" stroke-width="3"/><path d="M42 92L132 29" stroke="#f4511e" stroke-width="4"/></g></svg>`,
  tool: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-30 90 60)"><rect x="52" y="28" width="76" height="22" rx="8" fill="#3e434a"/><rect x="84" y="44" width="13" height="65" rx="5" fill="#f4511e"/><path d="M62 32V46M76 32V46M90 32V46M104 32V46M118 32V46" stroke="#dfe2e6" stroke-width="3"/></g></svg>`,
};

export function art(key) {
  return ART[key] || ART.tool;
}
