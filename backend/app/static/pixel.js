// Tiny pixel-art engine: each icon is a 12x12 text grid, rendered as crisp SVG.
// Usage in HTML: <i data-pixel="shield" data-size="48"></i>
const PALETTE = {
  k: "#14123a", o: "#f27a2b", t: "#27a69b", p: "#5b3fb0", c: "#f4ead2",
  y: "#ffc93c", w: "#ffffff", r: "#e23d3d", g: "#3fbf6a",
};

const ICONS = {
  smiley: [
    "....kkkk....", "..kkyyyykk..", ".kyyyyyyyyk.", ".kyykyykyyk.",
    "kyyykyykyyyk", "kyyyyyyyyyyk", "kykyyyyyykyk", "kyykyyyykyyk",
    ".kyykkkkyyk.", ".kyyyyyyyyk.", "..kkyyyykk..", "....kkkk....",
  ],
  shield: [
    "kkkkkkkkkkkk", "kttttttttttk", "kttttttttwtk", "ktttttttwttk",
    "kwtttttwtttk", "ktwtttwttttk", "kttwtwtttttk", ".kttwtttttk.",
    ".kttttttttk.", "..kttttttk..", "...kttttk...", "....kkkk....",
  ],
  search: [
    "..kkkk......", ".kcccck.....", "kwccccck....", "kwccccck....",
    "kcccccck....", "kcccccck....", ".kcccck.....", "..kkkkoo....",
    "......ooo...", ".......ooo..", "........ooo.", ".........oo.",
  ],
  chip: [
    "...k..k..k..", "..kkkkkkkkk.", "..kpppppppk.", "kkkpttttppkk",
    "..kpttttppk.", "..kpppppppk.", "kkkpppppppkk", "..kpooppppk.",
    "..kpppppppk.", "..kkkkkkkkk.", "...k..k..k..", "............",
  ],
  bubble: [
    ".kkkkkkkkkk.", "kcccccccccck", "kcpppppppcck", "kcccccccccck",
    "kcpppppcccck", "kcccccccccck", ".kkkkcckkkk.", ".....kck....",
    "......kk....", "............", "............", "............",
  ],
  chart: [
    "k...........", "k........oo.", "k........oo.", "k........oo.",
    "k.....tt.oo.", "k.....tt.oo.", "k.....tt.oo.", "k..pp.tt.oo.",
    "k..pp.tt.oo.", "k..pp.tt.oo.", "kkkkkkkkkkkk", "............",
  ],
  warning: [
    ".....kk.....", "....kyyk....", "....kyyk....", "...kyyyyk...",
    "...kykkyk...", "..kyykkyyk..", "..kyykkyyk..", ".kyyykkyyyk.",
    ".kyyyyyyyyk.", "kyyyykkyyyyk", "kyyyyyyyyyyk", "kkkkkkkkkkkk",
  ],
  lock: [
    "...kkkkkk...", "..kk....kk..", "..k......k..", "..k......k..",
    "kkkkkkkkkkkk", "kooooooooook", "kooookkooook", "kooookkooook",
    "kooooooooook", "kooooooooook", "kkkkkkkkkkkk", "............",
  ],
  planet: [
    "....kkkk....", "..kkttttkk..", ".kttwtttttk.", ".ktwttttttk.",
    "ooktttttttko", "oooooooooooo", ".kttttttttoo", ".kttttttttk.",
    "..kkttttkk..", "....kkkk....", "............", "............",
  ],
};

function pixelSvg(name, size = 32) {
  const grid = ICONS[name];
  if (!grid) return "";
  let rects = "";
  grid.forEach((row, y) => [...row].forEach((ch, x) => {
    if (PALETTE[ch]) rects += `<rect x="${x}" y="${y}" width="1" height="1" fill="${PALETTE[ch]}"/>`;
  }));
  return `<svg viewBox="0 0 12 12" width="${size}" height="${size}" shape-rendering="crispEdges" aria-hidden="true">${rects}</svg>`;
}

function renderPixels(root = document) {
  root.querySelectorAll("[data-pixel]").forEach((el) => {
    el.innerHTML = pixelSvg(el.dataset.pixel, Number(el.dataset.size) || 32); // static, trusted icon data only
  });
}
document.addEventListener("DOMContentLoaded", () => renderPixels());
