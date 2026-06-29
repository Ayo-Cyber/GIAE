import type { GeneRow } from "./types";

// ── Types ─────────────────────────────────────────────────────────────────────

export type AmrCategory =
  | "beta-lactamase"
  | "aminoglycoside"
  | "tetracycline"
  | "fluoroquinolone"
  | "macrolide"
  | "chloramphenicol"
  | "sulfonamide"
  | "vancomycin"
  | "trimethoprim"
  | "colistin"
  | "efflux-pump"
  | "multi-drug";

export type VirulenceCategory =
  | "toxin"
  | "adhesin"
  | "invasion"
  | "iron-acquisition"
  | "capsule"
  | "secretion-system"
  | "immune-evasion"
  | "biofilm";

export interface AmrHit {
  type: "amr";
  category: AmrCategory;
  label: string;
  description: string;
  confidence: "high" | "moderate" | "heuristic";
}

export interface VirulenceHit {
  type: "virulence";
  category: VirulenceCategory;
  label: string;
  description: string;
  confidence: "high" | "moderate" | "heuristic";
}

export type BioHit = AmrHit | VirulenceHit;

// ── Rule format ───────────────────────────────────────────────────────────────
// Each rule: { patterns: string[] matched against name+function+pfam (lowercase),
//              hit: the BioHit to return on match }

interface Rule {
  patterns: string[];
  hit: BioHit;
}

// ── AMR rules ─────────────────────────────────────────────────────────────────

const AMR_RULES: Rule[] = [
  // Beta-lactamases
  { patterns: ["tem-", "tem1", "tem2", "blaTEM", "bla_tem"],
    hit: { type:"amr", category:"beta-lactamase", label:"TEM β-lactamase", description:"Extended-spectrum β-lactamase; confers resistance to penicillins and early cephalosporins.", confidence:"high" } },
  { patterns: ["shv-", "blaSHV", "bla_shv"],
    hit: { type:"amr", category:"beta-lactamase", label:"SHV β-lactamase", description:"ESBL commonly found in Klebsiella; resistance to penicillins and cephalosporins.", confidence:"high" } },
  { patterns: ["ctx-m", "blaCTX", "bla_ctx"],
    hit: { type:"amr", category:"beta-lactamase", label:"CTX-M β-lactamase", description:"Most prevalent ESBL worldwide; high-level cephalosporin resistance.", confidence:"high" } },
  { patterns: ["ndm-", "blaNDM", "bla_ndm", "new delhi metallo"],
    hit: { type:"amr", category:"beta-lactamase", label:"NDM metallo-β-lactamase", description:"Carbapenem resistance; associated with pan-drug resistance.", confidence:"high" } },
  { patterns: ["kpc-", "blaKPC", "bla_kpc", "klebsiella pneumoniae carbapenemase"],
    hit: { type:"amr", category:"beta-lactamase", label:"KPC carbapenemase", description:"Carbapenem resistance; high clinical significance.", confidence:"high" } },
  { patterns: ["vim-", "blaVIM", "bla_vim"],
    hit: { type:"amr", category:"beta-lactamase", label:"VIM metallo-β-lactamase", description:"Carbapenem resistance commonly found in Pseudomonas.", confidence:"high" } },
  { patterns: ["imp-", "blaIMP"],
    hit: { type:"amr", category:"beta-lactamase", label:"IMP metallo-β-lactamase", description:"Carbapenem resistance; integron-associated.", confidence:"high" } },
  { patterns: ["oxa-", "blaOXA"],
    hit: { type:"amr", category:"beta-lactamase", label:"OXA β-lactamase", description:"Oxacillinase; some variants confer carbapenem resistance.", confidence:"high" } },
  { patterns: ["beta-lactamase", "penicillinase", "cephalosporinase", "carbapenemase", "PF13354", "PF00144"],
    hit: { type:"amr", category:"beta-lactamase", label:"β-lactamase", description:"Hydrolyses β-lactam ring; broad-spectrum resistance.", confidence:"moderate" } },

  // Aminoglycosides
  { patterns: ["aph(3", "aph(6", "aph(2", "aminoglycoside phosphotransferase"],
    hit: { type:"amr", category:"aminoglycoside", label:"APH phosphotransferase", description:"Phosphorylates aminoglycosides; resistance to kanamycin, neomycin.", confidence:"high" } },
  { patterns: ["aac(6", "aac(3", "aac(2", "aminoglycoside acetyltransferase"],
    hit: { type:"amr", category:"aminoglycoside", label:"AAC acetyltransferase", description:"Acetylates aminoglycosides; resistance to gentamicin, tobramycin.", confidence:"high" } },
  { patterns: ["ant(2", "ant(3", "ant(4", "aminoglycoside nucleotidyltransferase"],
    hit: { type:"amr", category:"aminoglycoside", label:"ANT nucleotidyltransferase", description:"Adenylylates aminoglycosides; resistance to streptomycin, spectinomycin.", confidence:"high" } },
  { patterns: ["aada", "streptomycin adenylyltransferase"],
    hit: { type:"amr", category:"aminoglycoside", label:"AadA streptomycin resistance", description:"Adenylylates streptomycin and spectinomycin.", confidence:"high" } },
  { patterns: ["rmtb", "rmta", "16s rrna methyltransferase", "aminoglycoside resistance methyltransferase"],
    hit: { type:"amr", category:"aminoglycoside", label:"16S rRNA methyltransferase", description:"Methylates 16S rRNA; pan-aminoglycoside resistance.", confidence:"high" } },

  // Tetracycline
  { patterns: ["tet(a)", "teta ", "tetracycline efflux", "tet efflux"],
    hit: { type:"amr", category:"tetracycline", label:"TetA efflux pump", description:"Major facilitator superfamily efflux; tetracycline resistance.", confidence:"high" } },
  { patterns: ["tet(m)", "tetm ", "tet(o)", "teto ", "tetracycline ribosomal protection"],
    hit: { type:"amr", category:"tetracycline", label:"Tet ribosomal protection", description:"Protects ribosome from tetracycline; broad tetracycline resistance.", confidence:"high" } },
  { patterns: ["tetracycline resistance", "tetracycline-resistance"],
    hit: { type:"amr", category:"tetracycline", label:"Tetracycline resistance", description:"Tetracycline resistance determinant.", confidence:"moderate" } },

  // Fluoroquinolones
  { patterns: ["qnra", "qnrb", "qnrs", "qnrc", "quinolone resistance", "pentapeptide repeat"],
    hit: { type:"amr", category:"fluoroquinolone", label:"Qnr quinolone resistance", description:"Protects DNA gyrase from quinolone inhibition.", confidence:"high" } },
  { patterns: ["aac(6')-ib-cr", "fluoroquinolone acetyltransferase"],
    hit: { type:"amr", category:"fluoroquinolone", label:"AAC(6')-Ib-cr", description:"Acetyltransferase with activity against fluoroquinolones.", confidence:"high" } },

  // Macrolides
  { patterns: ["erma", "ermb", "ermc", "erm(a)", "erm(b)", "erm(c)", "23s rrna methyltransferase", "macrolide resistance methyltransferase"],
    hit: { type:"amr", category:"macrolide", label:"Erm rRNA methyltransferase", description:"Methylates 23S rRNA; MLSB resistance (macrolides, lincosamides, streptogramins).", confidence:"high" } },
  { patterns: ["mefa", "mef(a)", "macrolide efflux"],
    hit: { type:"amr", category:"macrolide", label:"MefA macrolide efflux", description:"Efflux of 14- and 15-membered macrolides.", confidence:"high" } },

  // Chloramphenicol
  { patterns: ["cat ", "cata", "catb", "chloramphenicol acetyltransferase"],
    hit: { type:"amr", category:"chloramphenicol", label:"CAT chloramphenicol acetyltransferase", description:"Inactivates chloramphenicol by acetylation.", confidence:"high" } },
  { patterns: ["cmla", "cml ", "chloramphenicol efflux"],
    hit: { type:"amr", category:"chloramphenicol", label:"CmlA chloramphenicol efflux", description:"Exports chloramphenicol; inducible resistance.", confidence:"high" } },

  // Sulfonamides
  { patterns: ["sul1", "sul2", "sul3", "dihydropteroate synthase", "sulfonamide resistance"],
    hit: { type:"amr", category:"sulfonamide", label:"Sul sulfonamide resistance", description:"Drug-insensitive dihydropteroate synthase; sulfonamide resistance.", confidence:"high" } },

  // Vancomycin
  { patterns: ["vana", "vanb", "vanc", "van(a)", "van(b)", "vancomycin resistance", "d-ala-d-lac", "d-ala-d-ser"],
    hit: { type:"amr", category:"vancomycin", label:"Van vancomycin resistance", description:"Reprograms cell-wall precursors; resistance to glycopeptides.", confidence:"high" } },

  // Trimethoprim
  { patterns: ["dfra", "dfrb", "dhfr", "dihydrofolate reductase", "trimethoprim resistance"],
    hit: { type:"amr", category:"trimethoprim", label:"DHFR trimethoprim resistance", description:"Drug-insensitive dihydrofolate reductase; trimethoprim resistance.", confidence:"high" } },

  // Colistin
  { patterns: ["mcr-1", "mcr-2", "mcr1", "mcr2", "phosphoethanolamine transferase", "colistin resistance"],
    hit: { type:"amr", category:"colistin", label:"MCR colistin resistance", description:"Modifies lipid A; resistance to polymyxins.", confidence:"high" } },

  // Efflux pumps
  { patterns: ["acrb", "acrab", "mexb", "mexab", "tolc", "multidrug efflux", "rnd efflux", "resistance-nodulation-division"],
    hit: { type:"amr", category:"efflux-pump", label:"RND efflux pump", description:"Resistance-nodulation-division transporter; broad-spectrum efflux.", confidence:"moderate" } },
  { patterns: ["nora", "mura", "smr efflux", "small multidrug resistance"],
    hit: { type:"amr", category:"efflux-pump", label:"SMR efflux pump", description:"Small multidrug resistance transporter.", confidence:"moderate" } },
  { patterns: ["mdra", "mdrb", "mdr transporter", "multidrug resistance protein", "PF00664"],
    hit: { type:"amr", category:"multi-drug", label:"MDR transporter", description:"ATP-binding cassette multidrug resistance transporter.", confidence:"moderate" } },
];

// ── Virulence rules ───────────────────────────────────────────────────────────

const VIRULENCE_RULES: Rule[] = [
  // Toxins
  { patterns: ["stx1", "stx2", "shiga toxin", "shiga-like toxin", "verotoxin"],
    hit: { type:"virulence", category:"toxin", label:"Shiga toxin", description:"AB-type toxin; inhibits protein synthesis; associated with HUS.", confidence:"high" } },
  { patterns: ["hlyA", "hlya", "alpha-hemolysin", "hemolysin a", "pore-forming toxin", "cytolysin"],
    hit: { type:"virulence", category:"toxin", label:"Hemolysin / cytolysin", description:"Pore-forming toxin; lyses erythrocytes and nucleated cells.", confidence:"high" } },
  { patterns: ["ctx", "cholera toxin", "heat-labile enterotoxin", "ltab", "lt toxin"],
    hit: { type:"virulence", category:"toxin", label:"Cholera / LT enterotoxin", description:"ADP-ribosylating AB5 toxin; activates adenylate cyclase.", confidence:"high" } },
  { patterns: ["sta", "stb", "heat-stable enterotoxin", "enterotoxin st"],
    hit: { type:"virulence", category:"toxin", label:"Heat-stable enterotoxin", description:"Activates guanylate cyclase; watery diarrhoea.", confidence:"high" } },
  { patterns: ["pntoxin", "pertussis toxin", "adenylate cyclase toxin", "cya toxin"],
    hit: { type:"virulence", category:"toxin", label:"Pertussis / adenylate cyclase toxin", description:"Increases cAMP; impairs immune response.", confidence:"high" } },
  { patterns: ["botulinum", "tetanus toxin", "neurotoxin"],
    hit: { type:"virulence", category:"toxin", label:"Clostridial neurotoxin", description:"Metalloprotease cleaving SNARE proteins; blocks neurotransmission.", confidence:"high" } },
  { patterns: ["leukotoxin", "leukocidin", "pvl", "panton-valentine"],
    hit: { type:"virulence", category:"toxin", label:"Leukotoxin / PVL", description:"Pore-forming toxin targeting leukocytes; community MRSA virulence.", confidence:"high" } },
  { patterns: ["exotoxin", "enterotoxin", "cytotoxin", "toxic shock"],
    hit: { type:"virulence", category:"toxin", label:"Toxin", description:"Bacterial toxin contributing to pathogenesis.", confidence:"heuristic" } },

  // Adhesins
  { patterns: ["fimH", "fimh", "type 1 fimbria", "type i fimbrial"],
    hit: { type:"virulence", category:"adhesin", label:"FimH type-1 fimbrial adhesin", description:"Mannose-binding adhesin; critical for UTI pathogenesis.", confidence:"high" } },
  { patterns: ["papG", "papg", "pap fimbriae", "p fimbria", "galabiose-binding"],
    hit: { type:"virulence", category:"adhesin", label:"PapG P-fimbrial adhesin", description:"Galabiose-binding adhesin; pyelonephritis virulence factor.", confidence:"high" } },
  { patterns: ["afaD", "afaE", "afa adhesin", "dr fimbria", "diffuse adhering"],
    hit: { type:"virulence", category:"adhesin", label:"Afa/Dr adhesin", description:"DAF-binding adhesin; involved in urinary and intestinal infection.", confidence:"high" } },
  { patterns: ["intimin", "eae gene", "tir protein"],
    hit: { type:"virulence", category:"adhesin", label:"Intimin / Tir", description:"Outer membrane adhesin for intimate EPEC/EHEC attachment.", confidence:"high" } },
  { patterns: ["invasin", "inv gene", "yersinia invasin"],
    hit: { type:"virulence", category:"adhesin", label:"Invasin", description:"β1-integrin–binding adhesin; promotes bacterial uptake.", confidence:"high" } },
  { patterns: ["msba", "mscl", "surface protein", "adhesin", "hemagglutinin"],
    hit: { type:"virulence", category:"adhesin", label:"Surface adhesin", description:"Surface-exposed protein mediating host-cell attachment.", confidence:"heuristic" } },

  // Invasion
  { patterns: ["spaa", "spab", "spac", "spi-1", "hilA", "hila", "salmonella pathogenicity"],
    hit: { type:"virulence", category:"invasion", label:"SPI-1 invasion effector", description:"Salmonella Pathogenicity Island 1; triggers membrane ruffling and invasion.", confidence:"high" } },
  { patterns: ["ipab", "ipac", "ipah", "ipa protein", "shigella invasion"],
    hit: { type:"virulence", category:"invasion", label:"Ipa invasion protein", description:"Shigella invasion plasmid antigen; triggers actin-mediated entry.", confidence:"high" } },
  { patterns: ["inlA", "inla", "inlB", "inlb", "internalin"],
    hit: { type:"virulence", category:"invasion", label:"Internalin", description:"Listeria surface protein mediating E-cadherin/Met-dependent invasion.", confidence:"high" } },
  { patterns: ["invasion protein", "host cell invasion", "actin polymerization"],
    hit: { type:"virulence", category:"invasion", label:"Invasion factor", description:"Promotes bacterial entry into non-phagocytic cells.", confidence:"heuristic" } },

  // Iron acquisition
  { patterns: ["irob", "iroc", "irod", "iroN", "salmochelin", "catecholate siderophore"],
    hit: { type:"virulence", category:"iron-acquisition", label:"Salmochelin siderophore", description:"Glucosylated enterobactin resists serum albumin sequestration.", confidence:"high" } },
  { patterns: ["fepA", "fepa", "entB", "enterobactin", "catecholate siderophore receptor"],
    hit: { type:"virulence", category:"iron-acquisition", label:"Enterobactin system", description:"High-affinity catecholate siderophore for iron scavenging.", confidence:"high" } },
  { patterns: ["iutA", "iuta", "iucA", "aerobactin", "hydroxamate siderophore"],
    hit: { type:"virulence", category:"iron-acquisition", label:"Aerobactin system", description:"Hydroxamate siderophore; important in extraintestinal infection.", confidence:"high" } },
  { patterns: ["tonB", "tonb", "exbb", "siderophore", "iron transport", "iron acquisition"],
    hit: { type:"virulence", category:"iron-acquisition", label:"Iron acquisition", description:"Iron uptake system; critical for infection in iron-limited host environment.", confidence:"heuristic" } },

  // Capsule
  { patterns: ["cps", "kps", "wzy", "wzx", "capsule polymerase", "capsular polysaccharide"],
    hit: { type:"virulence", category:"capsule", label:"Capsule biosynthesis", description:"Polysaccharide capsule protects from opsonisation and complement.", confidence:"high" } },
  { patterns: ["sia", "sial", "neuraminidase", "polysialic acid"],
    hit: { type:"virulence", category:"capsule", label:"Sialic acid / polysialic acid", description:"Mimics host glycans; evades immune recognition.", confidence:"high" } },

  // Secretion systems
  { patterns: ["type iii secretion", "type-iii secretion", "t3ss", "injectisome", "hrp", "hrpA", "hrpa"],
    hit: { type:"virulence", category:"secretion-system", label:"Type III secretion system", description:"Injectisome translocating effectors directly into host cell cytoplasm.", confidence:"high" } },
  { patterns: ["type iv secretion", "type-iv secretion", "t4ss", "virb", "tra gene", "conjugal transfer"],
    hit: { type:"virulence", category:"secretion-system", label:"Type IV secretion system", description:"Transfers effectors or DNA into host cells; also mediates conjugation.", confidence:"high" } },
  { patterns: ["type vi secretion", "type-vi secretion", "t6ss", "vgrg", "hcp", "spike protein secretion"],
    hit: { type:"virulence", category:"secretion-system", label:"Type VI secretion system", description:"Contractile nanomachine; injects toxins into competing bacteria or host cells.", confidence:"high" } },
  { patterns: ["type ii secretion", "gsp", "general secretion pathway", "xcp"],
    hit: { type:"virulence", category:"secretion-system", label:"Type II secretion system", description:"Secretes folded exoenzymes and toxins across the outer membrane.", confidence:"moderate" } },

  // Immune evasion
  { patterns: ["spa gene", "protein a", "staphylococcal protein a", "immunoglobulin-binding"],
    hit: { type:"virulence", category:"immune-evasion", label:"Protein A (IgG-binding)", description:"Binds Fc region of IgG; blocks opsonisation.", confidence:"high" } },
  { patterns: ["serum resistance", "complement evasion", "ompT", "protease iv", "outer membrane protease"],
    hit: { type:"virulence", category:"immune-evasion", label:"Serum / complement resistance", description:"Protects against complement-mediated killing in serum.", confidence:"heuristic" } },

  // Biofilm
  { patterns: ["icaA", "icaa", "icaB", "icab", "icaD", "icad", "pgna", "poly-n-acetylglucosamine", "biofilm polysaccharide"],
    hit: { type:"virulence", category:"biofilm", label:"Ica biofilm matrix", description:"Poly-N-acetylglucosamine (PNAG) synthesis; staphylococcal biofilm formation.", confidence:"high" } },
  { patterns: ["luxS", "luxs", "quorum sensing", "autoinducer", "AI-2"],
    hit: { type:"virulence", category:"biofilm", label:"Quorum sensing / LuxS", description:"Cell-density signalling; coordinates biofilm and virulence gene expression.", confidence:"moderate" } },
  { patterns: ["biofilm", "pellicle formation"],
    hit: { type:"virulence", category:"biofilm", label:"Biofilm factor", description:"Contributes to biofilm formation and persistence.", confidence:"heuristic" } },
];

// ── Matcher ───────────────────────────────────────────────────────────────────

function haystack(g: GeneRow): string {
  return [
    g.name,
    g.locus,
    g.function,
    g.normalized_product,
    g.pfam_id,
    g.cog_name,
    ...(g.go_terms ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function flagGene(g: GeneRow): BioHit[] {
  const hay = haystack(g);
  const hits: BioHit[] = [];
  const seen = new Set<string>();

  for (const rule of [...AMR_RULES, ...VIRULENCE_RULES]) {
    if (rule.patterns.some((p) => hay.includes(p.toLowerCase()))) {
      const key = rule.hit.label;
      if (!seen.has(key)) {
        seen.add(key);
        hits.push(rule.hit);
      }
    }
  }

  return hits;
}

export function flagGenes(genes: GeneRow[]): Map<string, BioHit[]> {
  const out = new Map<string, BioHit[]>();
  for (const g of genes) {
    const hits = flagGene(g);
    if (hits.length > 0) out.set(g.id, hits);
  }
  return out;
}

// ── Display helpers ───────────────────────────────────────────────────────────

export const AMR_CATEGORY_LABELS: Record<AmrCategory, string> = {
  "beta-lactamase":  "β-Lactamase",
  "aminoglycoside":  "Aminoglycoside",
  "tetracycline":    "Tetracycline",
  "fluoroquinolone": "Fluoroquinolone",
  "macrolide":       "Macrolide",
  "chloramphenicol": "Chloramphenicol",
  "sulfonamide":     "Sulfonamide",
  "vancomycin":      "Vancomycin",
  "trimethoprim":    "Trimethoprim",
  "colistin":        "Colistin",
  "efflux-pump":     "Efflux Pump",
  "multi-drug":      "Multi-drug",
};

export const VIRULENCE_CATEGORY_LABELS: Record<VirulenceCategory, string> = {
  "toxin":             "Toxin",
  "adhesin":           "Adhesin",
  "invasion":          "Invasion",
  "iron-acquisition":  "Iron Acquisition",
  "capsule":           "Capsule",
  "secretion-system":  "Secretion System",
  "immune-evasion":    "Immune Evasion",
  "biofilm":           "Biofilm",
};
