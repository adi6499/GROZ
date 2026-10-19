// Category illustrations from the approved V2 design reference. These are icons for categories and
// placeholders only -- they are never presented as photographs of a specific product.
// Parts with an "a-" class come alive when their category tile is hovered or focused (site.css,
// "category icons come alive"); elsewhere they stay still. Animated parts never carry a transform
// attribute of their own (a CSS transform would replace it), so they are wrapped in their own group.

const s = 'stroke-linecap="round" stroke-linejoin="round"';

const ART = {
  hammer: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-28 90 60)"><rect x="82" y="42" width="16" height="68" rx="7" fill="#f4511e"/><path d="M55 35Q55 27 64 27H119Q128 27 128 36V51Q128 59 119 59H64Q55 59 55 51Z" fill="#b9bec5" stroke="#737982" stroke-width="3"/><path d="M65 31H115" stroke="#fff" stroke-width="3"/></g></svg>`,
  // Hand Tools: the sledge swings back and taps, pivoting at the end of its handle.
  sledge: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g class="a-swing"><g transform="rotate(-37 90 60)"><rect x="82" y="34" width="16" height="80" rx="7" fill="#f4511e"/><rect x="45" y="19" width="90" height="31" rx="7" fill="#3d4148"/><rect x="51" y="22" width="78" height="5" rx="2" fill="#747982"/></g></g></svg>`,
  // Mechanic's Tools: the drawers slide out one after another.
  storage: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="translate(35 10)"><rect x="18" y="9" width="76" height="95" rx="5" fill="#27292e"/><rect class="a-drawer" style="--i:0" x="24" y="16" width="64" height="13" rx="2" fill="#f4511e"/><rect class="a-drawer" style="--i:1" x="24" y="34" width="64" height="13" rx="2" fill="#f4511e"/><rect class="a-drawer" style="--i:2" x="24" y="52" width="64" height="13" rx="2" fill="#f4511e"/><rect class="a-drawer" style="--i:3" x="24" y="70" width="64" height="13" rx="2" fill="#f4511e"/><circle cx="32" cy="108" r="6" fill="#454950"/><circle cx="81" cy="108" r="6" fill="#454950"/></g></svg>`,
  // Lighting: the lamp switches on, with a warm glow behind it.
  light: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><circle class="a-glow" cx="88" cy="54" r="42" fill="#ffd36b"/><g transform="rotate(-22 90 60)"><rect x="58" y="25" width="65" height="58" rx="9" fill="#30343a"/><rect class="a-lens" x="66" y="33" width="49" height="42" rx="5" fill="#dce7ef"/><path d="M72 39L109 69M109 39L72 69" stroke="#fff" stroke-width="3"/><rect x="81" y="82" width="20" height="23" rx="5" fill="#f4511e"/></g></svg>`,
  // Precision Tools: the measuring line draws itself across the scale.
  measure: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-12 90 60)"><path d="M42 29H132V92H42Z" fill="#cfd4da" stroke="#6c727b" stroke-width="3"/><path d="M51 39V53M63 39V48M75 39V53M87 39V48M99 39V53M111 39V48M123 39V53" stroke="#4e535b" stroke-width="3"/><path class="a-line" d="M42 92L132 29" stroke="#f4511e" stroke-width="4"/></g></svg>`,
  // GROZ categories that are not in this preview yet (same style, drawn for this site).
  // Lubrication: the lever pumps and grease drips from the nozzle.
  grease: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-14 90 60)"><rect x="38" y="44" width="13" height="18" rx="3" fill="#3d4148"/><rect x="49" y="38" width="80" height="30" rx="9" fill="#b9bec5" stroke="#737982" stroke-width="3"/><path d="M57 45H121" stroke="#fff" stroke-width="3"/><rect x="127" y="44" width="14" height="18" rx="3" fill="#3d4148"/><path d="M141 53H163" stroke="#3d4148" stroke-width="5"/><circle class="a-drop" cx="165" cy="57" r="3.5" fill="#c98a1b"/><path class="a-lever" d="M131 64L112 100" stroke="#f4511e" stroke-width="11"/></g></svg>`,
  // Fuel & DEF: the trigger squeezes and fuel drips from the spout.
  fuel: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-10 90 60)"><path d="M118 44H146Q156 44 158 54L160 64" fill="none" stroke="#b9bec5" stroke-width="9"/><circle class="a-drop" cx="160" cy="71" r="3.5" fill="#e8a33a"/><path d="M48 40Q48 31 57 31H112Q121 31 121 40V57Q121 66 112 66H97L90 96Q89 102 83 102H72Q66 102 67 96L73 66H57Q48 66 48 57Z" fill="#3d4148"/><rect x="56" y="38" width="44" height="8" rx="3" fill="#f4511e"/><path class="a-trigger" d="M80 72Q91 82 96 72" fill="none" stroke="#f4511e" stroke-width="6"/></g></svg>`,
  // Air Tools: the wrench buzzes and puffs of air come out.
  air: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-8 90 60)"><g class="a-buzz"><rect x="44" y="28" width="82" height="36" rx="15" fill="#3d4148"/><rect x="124" y="35" width="16" height="22" rx="4" fill="#b9bec5" stroke="#737982" stroke-width="2"/><rect x="140" y="40" width="11" height="12" rx="1" fill="#737982"/><path d="M62 62L54 100Q53 107 60 107H76Q82 107 83 101L90 62Z" fill="#f4511e"/><path d="M88 70Q99 73 96 84" fill="none" stroke="#b9bec5" stroke-width="4"/></g><path d="M58 107Q50 115 36 112" fill="none" stroke="#737982" stroke-width="4"/><circle class="a-puff" style="--i:0" cx="160" cy="46" r="5" fill="#c9ced6"/><circle class="a-puff" style="--i:1" cx="166" cy="38" r="4" fill="#c9ced6"/></g></svg>`,
  // Power Tools: the drill buzzes and its bit spins.
  drill: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-8 90 60)"><g class="a-buzz"><path d="M54 28H120Q131 28 131 39V51Q131 61 120 61H101L95 88H70L77 61H58Q47 61 47 50V39Q47 28 54 28Z" fill="#f4511e"/><rect x="58" y="35" width="38" height="6" rx="3" fill="#ffb08f"/><rect x="63" y="86" width="46" height="19" rx="5" fill="#3d4148"/><rect x="131" y="37" width="17" height="15" rx="3" fill="#3d4148"/></g><path class="a-bit" d="M148 44.5H168" stroke="#b9bec5" stroke-width="4"/></g></svg>`,
  // New & Exciting: the star turns and the sparkles twinkle.
  spark: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><path class="a-star" d="M90 16L101 46L133 48L108 68L117 99L90 81L63 99L72 68L47 48L79 46Z" fill="#f4511e"/><path class="a-twinkle" style="--i:0" d="M141 22L145 33L156 37L145 41L141 52L137 41L126 37L137 33Z" fill="#ffad8a"/><path class="a-twinkle" style="--i:1" d="M38 78L41 86L49 89L41 92L38 100L35 92L27 89L35 86Z" fill="#3d4148"/></svg>`,
  tool: `<svg viewBox="0 0 180 120" ${s} aria-hidden="true"><g transform="rotate(-30 90 60)"><rect x="52" y="28" width="76" height="22" rx="8" fill="#3e434a"/><rect x="84" y="44" width="13" height="65" rx="5" fill="#f4511e"/><path d="M62 32V46M76 32V46M90 32V46M104 32V46M118 32V46" stroke="#dfe2e6" stroke-width="3"/></g></svg>`,
};

export function art(key) {
  return ART[key] || ART.tool;
}
