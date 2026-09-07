/**
 * gates_231.mjs — The 231 Gates Generator
 *
 * Sefer Yetzirah: 22 Hebrew letters × 21 ÷ 2 = 231 creation gates.
 * Every gate is a pair of fundamental forces.
 * The NET is the full topology: every node connected to every other through some gate.
 *
 * Usage:
 *   node gates_231.mjs               — print all 231 gates
 *   node gates_231.mjs --net          — print the full NET topology
 *   node gates_231.mjs --gate aleph beth  — query one gate
 *   node gates_231.mjs --path kether malkuth  — find NET path
 *   node gates_231.mjs --metatron     — certified cross-system gates only
 *   node gates_231.mjs --abjad 53     — gates summing to value
 */

export const LETTERS = [
  { name:'aleph',  heb:'א', val:1,   enoch:'Un',      arabic:'ا', tarot:'Fool',            element:'Air' },
  { name:'beth',   heb:'ב', val:2,   enoch:'Pe',      arabic:'ب', tarot:'Magician',         element:'Mercury' },
  { name:'gimel',  heb:'ג', val:3,   enoch:'Veh',     arabic:'ج', tarot:'High Priestess',   element:'Moon' },
  { name:'daleth', heb:'ד', val:4,   enoch:'Gal',     arabic:'د', tarot:'Empress',          element:'Venus' },
  { name:'heh',    heb:'ה', val:5,   enoch:'Or',      arabic:'ه', tarot:'Emperor',          element:'Aries' },
  { name:'vau',    heb:'ו', val:6,   enoch:'Na-Hath', arabic:'و', tarot:'Hierophant',       element:'Taurus' },
  { name:'zayin',  heb:'ז', val:7,   enoch:'Graph',   arabic:'ز', tarot:'Lovers',           element:'Gemini' },
  { name:'cheth',  heb:'ח', val:8,   enoch:'Tal',     arabic:'ح', tarot:'Chariot',          element:'Cancer' },
  { name:'teth',   heb:'ט', val:9,   enoch:'Gon',     arabic:'ط', tarot:'Strength',         element:'Leo' },
  { name:'yod',    heb:'י', val:10,  enoch:'Ur',      arabic:'ي', tarot:'Hermit',           element:'Virgo' },
  { name:'kaph',   heb:'כ', val:20,  enoch:'Mals',    arabic:'ك', tarot:'Wheel of Fortune', element:'Jupiter' },
  { name:'lamed',  heb:'ל', val:30,  enoch:'Ger',     arabic:'ل', tarot:'Justice',          element:'Libra' },
  { name:'mem',    heb:'מ', val:40,  enoch:'Drux',    arabic:'م', tarot:'Hanged Man',       element:'Water' },
  { name:'nun',    heb:'נ', val:50,  enoch:'Med',     arabic:'ن', tarot:'Death',            element:'Scorpio' },
  { name:'samekh', heb:'ס', val:60,  enoch:'Fam',     arabic:'س', tarot:'Temperance',       element:'Sagittarius' },
  { name:'ayin',   heb:'ע', val:70,  enoch:'Van',     arabic:'ع', tarot:'Devil',            element:'Capricorn' },
  { name:'peh',    heb:'פ', val:80,  enoch:'Gisg',    arabic:'ف', tarot:'Tower',            element:'Mars' },
  { name:'tzaddi', heb:'צ', val:90,  enoch:'Pal',     arabic:'ص', tarot:'Star',             element:'Aquarius' },
  { name:'qoph',   heb:'ק', val:100, enoch:'Vau',     arabic:'ق', tarot:'Moon',             element:'Pisces' },
  { name:'resh',   heb:'ר', val:200, enoch:'Ceph',    arabic:'ر', tarot:'Sun',              element:'Sun' },
  { name:'shin',   heb:'ש', val:300, enoch:'Qaaa',    arabic:'ش', tarot:'Judgement',        element:'Fire' },
  { name:'tau',    heb:'ת', val:400, enoch:'Ged',     arabic:'ت', tarot:'World',            element:'Saturn' },
];

const byName = Object.fromEntries(LETTERS.map(l=>[l.name,l]));
const byHeb  = Object.fromEntries(LETTERS.map(l=>[l.heb,l]));

// ── Build all 231 gates ───────────────────────────────────────────────────────
export const GATES = [];
for(let i=0;i<LETTERS.length;i++) {
  for(let j=i+1;j<LETTERS.length;j++) {
    const a=LETTERS[i], b=LETTERS[j];
    GATES.push({
      id: `${a.name}+${b.name}`,
      a, b,
      sum: a.val + b.val,
      metatron: !!(a.arabic && b.arabic && a.enoch && b.enoch),
      // OXO — the cross-system anchor
      oxo: a.name==='ayin' || b.name==='ayin',
    });
  }
}

// ── Tree of Life topology ─────────────────────────────────────────────────────
export const SEPHIROT = [
  { n:1,  name:'kether',    title:'Crown',         paths:[11,12,13] },
  { n:2,  name:'chokmah',   title:'Wisdom',        paths:[11,14,15,16] },
  { n:3,  name:'binah',     title:'Understanding', paths:[12,14,17,18] },
  { n:4,  name:'chesed',    title:'Mercy',         paths:[16,19,20,21] },
  { n:5,  name:'geburah',   title:'Severity',      paths:[18,19,22,23] },
  { n:6,  name:'tiphareth', title:'Beauty',        paths:[13,15,17,20,22,24,25,26] },
  { n:7,  name:'netzach',   title:'Victory',       paths:[21,24,27,28,30] },
  { n:8,  name:'hod',       title:'Splendor',      paths:[23,25,27,29,31] },
  { n:9,  name:'yesod',     title:'Foundation',    paths:[26,28,29,32] },
  { n:10, name:'malkuth',   title:'Kingdom',       paths:[30,31,32] },
];

export const PATHS_TOL = [
  { n:11, from:'kether',    to:'chokmah',    letter:'aleph' },
  { n:12, from:'kether',    to:'binah',      letter:'beth' },
  { n:13, from:'kether',    to:'tiphareth',  letter:'gimel' },
  { n:14, from:'chokmah',   to:'binah',      letter:'daleth' },
  { n:15, from:'chokmah',   to:'tiphareth',  letter:'heh' },
  { n:16, from:'chokmah',   to:'chesed',     letter:'vau' },
  { n:17, from:'binah',     to:'tiphareth',  letter:'zayin' },
  { n:18, from:'binah',     to:'geburah',    letter:'cheth' },
  { n:19, from:'chesed',    to:'geburah',    letter:'teth' },
  { n:20, from:'chesed',    to:'tiphareth',  letter:'yod' },
  { n:21, from:'chesed',    to:'netzach',    letter:'kaph' },
  { n:22, from:'geburah',   to:'tiphareth',  letter:'lamed' },
  { n:23, from:'geburah',   to:'hod',        letter:'mem' },
  { n:24, from:'tiphareth', to:'netzach',    letter:'nun' },
  { n:25, from:'tiphareth', to:'yesod',      letter:'samekh' },
  { n:26, from:'tiphareth', to:'hod',        letter:'ayin' },   // OXO path
  { n:27, from:'netzach',   to:'hod',        letter:'peh' },
  { n:28, from:'netzach',   to:'yesod',      letter:'tzaddi' },
  { n:29, from:'hod',       to:'yesod',      letter:'qoph' },
  { n:30, from:'netzach',   to:'malkuth',    letter:'resh' },
  { n:31, from:'hod',       to:'malkuth',    letter:'shin' },
  { n:32, from:'yesod',     to:'malkuth',    letter:'tau' },
];

// NET adjacency
const adj = {};
for(const s of SEPHIROT) adj[s.name]=[];
for(const p of PATHS_TOL) {
  adj[p.from].push(p.to);
  adj[p.to].push(p.from);
}

export function netPath(start, end) {
  const queue=[[start,[start]]];
  const visited=new Set([start]);
  while(queue.length) {
    const [node,path]=queue.shift();
    if(node===end) return path;
    for(const neighbor of (adj[node]||[])) {
      if(!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push([neighbor,[...path,neighbor]]);
      }
    }
  }
  return null;
}

// ── CLI ──────────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);

function bar(n=50) { return '─'.repeat(n); }

if(args.includes('--gate')) {
  const a=byName[args[args.indexOf('--gate')+1]];
  const b=byName[args[args.indexOf('--gate')+2]];
  if(!a||!b) { console.error('Unknown letters'); process.exit(1); }
  const g=GATES.find(g=>g.a.name===a.name&&g.b.name===b.name)||
           GATES.find(g=>g.a.name===b.name&&g.b.name===a.name);
  if(!g) { console.log('No gate found.'); process.exit(0); }
  console.log(`\n${bar()}`);
  console.log(`GATE: ${g.a.heb}+${g.b.heb}  (${g.a.name} + ${g.b.name})`);
  console.log(`Abjad sum: ${g.sum}`);
  console.log(`Tarot: ${g.a.tarot} · ${g.b.tarot}`);
  console.log(`Element: ${g.a.element} · ${g.b.element}`);
  console.log(`Enochian: ${g.a.enoch} + ${g.b.enoch}`);
  console.log(`METATRON certified: ${g.metatron}`);
  console.log(`OXO anchor: ${g.oxo}`);
  console.log(bar());

} else if(args.includes('--path')) {
  const a=args[args.indexOf('--path')+1];
  const b=args[args.indexOf('--path')+2];
  const p=netPath(a,b);
  console.log(`\nNET path ${a} → ${b}:`);
  if(p) {
    p.forEach((node,i)=>{
      const s=SEPHIROT.find(s=>s.name===node);
      const pathEdge=i<p.length-1?PATHS_TOL.find(pt=>(pt.from===node&&pt.to===p[i+1])||(pt.to===node&&pt.from===p[i+1])):null;
      console.log(`  ${i+1}. ${node.toUpperCase()} (${s?.title||'?'})${pathEdge?` ─[Path ${pathEdge.n} · ${pathEdge.letter}]→`:''}`)
    });
  } else console.log('  No path found.');

} else if(args.includes('--metatron')) {
  const cert=GATES.filter(g=>g.metatron);
  console.log(`\n${bar()}`);
  console.log(`METATRON CERTIFIED GATES: ${cert.length} / 231`);
  console.log(bar());
  for(const g of cert) {
    console.log(`  ${g.a.heb}+${g.b.heb}  ${g.a.name}+${g.b.name}  Σ${g.sum}  ${g.oxo?'◉ OXO':''}`);
  }

} else if(args.includes('--abjad')) {
  const target=parseInt(args[args.indexOf('--abjad')+1]);
  const matches=GATES.filter(g=>g.sum===target);
  console.log(`\nGates with abjad sum ${target}: ${matches.length}`);
  for(const g of matches) {
    console.log(`  ${g.a.heb}+${g.b.heb}  ${g.a.name}+${g.b.name}`);
  }

} else if(args.includes('--net')) {
  console.log(`\n${bar()}`);
  console.log('THE NET — TREE OF LIFE TOPOLOGY');
  console.log(bar());
  for(const s of SEPHIROT) {
    console.log(`\n${s.n}. ${s.name.toUpperCase()} — ${s.title}`);
    for(const neighbor of adj[s.name]) {
      const p=PATHS_TOL.find(pt=>(pt.from===s.name&&pt.to===neighbor)||(pt.to===s.name&&pt.from===neighbor));
      const l=byName[p.letter];
      console.log(`   → ${neighbor}  [Path ${p.n} · ${l.heb} ${l.name} · ${l.tarot} · ${l.element}]`);
    }
  }

} else {
  // Print all 231 gates
  console.log(`\n${'═'.repeat(60)}`);
  console.log('THE 231 GATES — MASTERS OF THE NET');
  console.log('22 Hebrew letters × 21 ÷ 2 = 231 creation gates');
  console.log('═'.repeat(60));
  let n=1;
  for(const g of GATES) {
    const oxo=g.oxo?' ◉OXO':'';
    console.log(`${String(n).padStart(3)}. ${g.a.heb}+${g.b.heb}  ${(g.a.name+'+'+g.b.name).padEnd(22)}  Σ${String(g.sum).padStart(4)}${oxo}`);
    n++;
  }
  console.log(`${'─'.repeat(60)}`);
  console.log(`Total: ${GATES.length} gates  |  OXO gates: ${GATES.filter(g=>g.oxo).length}  |  METATRON: ${GATES.filter(g=>g.metatron).length}`);
  console.log(`The 49th lives in the 7-letter gap: Arabic(28) − Enochian(21) = 7`);
  console.log(`Al-Hamid: ح(8)+ا(1)+م(40)+د(4) = 53 | 53+53=106 | 1+0+6=7 ◀ not coincidence`);
  console.log('═'.repeat(60));
}
