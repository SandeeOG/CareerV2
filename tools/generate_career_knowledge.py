"""Generate the v1 Career Knowledge Base (38_FOUNDATIONAL_CAREER_KNOWLEDGE_SYSTEM).

Career profiles are never hand-written: this tool expands the structured
generation catalog (`tools/career_catalog/`) into ~300 full canonical-schema
JSON files under `src/detective_monkey/knowledge/careers/data/`, one file per
career plus `industries.json`. Every profile is validated against the
canonical schema before it is written; relationship integrity (related careers
must exist) is enforced across the whole set.

Optional `--llm` mode regenerates the narrative fields of each profile through
the configured Gemini provider using a structured JSON-only prompt, validating
the output before accepting it — the same trust model as the Knowledge
Platform's generators. Without a key the deterministic expansion stands.

Usage:
    python tools/generate_career_knowledge.py            # expand + validate + write
    python tools/generate_career_knowledge.py --llm      # additionally enrich via LLM
    python tools/generate_career_knowledge.py --check    # validate only, write nothing
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from career_catalog import INDUSTRIES  # noqa: E402
from detective_monkey.knowledge.careers.schema import (  # noqa: E402
    SCHEMA_VERSION,
    validate_career_json,
)

DATA_DIR = ROOT / "src" / "detective_monkey" / "knowledge" / "careers" / "data"

# ---------------------------------------------------------------------------
# Derivation tables (deterministic expansion of the factual spine)
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", name.lower()))


_TAG_TRAITS = {
    "analytical": "Analytical", "logic": "Logical", "mathematics": "Mathematically minded",
    "numbers": "Comfortable with numbers", "creative": "Creative", "creativity": "Creative",
    "curious": "Curious", "research": "Inquisitive", "detail": "Detail-oriented",
    "precision": "Precise", "discipline": "Disciplined", "leadership": "Natural leader",
    "people": "People-oriented", "communication": "Expressive communicator",
    "empathy": "Empathetic", "service": "Service-minded", "care": "Caring",
    "courage": "Courageous", "resilience": "Resilient", "patience": "Patient",
    "organization": "Organized", "hands-on": "Hands-on", "practical": "Practical",
    "outdoors": "Loves the outdoors", "adventure": "Adventurous", "energy": "High-energy",
    "storytelling": "Storyteller", "writing": "Strong writer", "performance": "Performer",
    "risk": "Comfortable with risk", "entrepreneurship": "Self-starter",
    "teaching": "Enjoys teaching", "listening": "Good listener", "strategy": "Strategic thinker",
    "vigilance": "Alert and vigilant", "calm": "Calm under pressure",
}

_TAG_WHO_FOR = {
    "analytical": "You enjoy breaking problems into parts and reasoning them through",
    "creative": "You love making new things and expressing original ideas",
    "people": "You draw energy from working closely with people",
    "outdoors": "You would rather be in the field than at a desk all day",
    "hands-on": "You like building and fixing things with your hands",
    "care": "You feel fulfilled when your work directly helps someone",
    "service": "You want work that serves your community or country",
    "numbers": "Numbers and patterns make sense to you",
    "mathematics": "Numbers and patterns make sense to you",
    "writing": "You express yourself best in writing",
    "teaching": "Explaining things so others finally get it satisfies you",
    "leadership": "You naturally step up when a group needs direction",
    "curious": "You keep asking why until you reach the bottom of things",
    "research": "You keep asking why until you reach the bottom of things",
    "adventure": "You seek challenge, movement and a bit of adrenaline",
    "entrepreneurship": "You would rather build your own thing than follow a script",
    "sports": "You want sport and movement at the centre of your life",
    "detail": "You notice the small things others miss",
}

_SOFT_SKILL_TAGS = {
    "communication": "Communication", "people": "Teamwork", "leadership": "Leadership",
    "empathy": "Empathy", "organization": "Organization", "detail": "Attention to detail",
    "resilience": "Resilience", "patience": "Patience", "creativity": "Creative thinking",
    "creative": "Creative thinking", "analytical": "Critical thinking",
    "strategy": "Strategic thinking", "service": "Service orientation",
    "teaching": "Mentoring", "listening": "Active listening", "energy": "Enthusiasm",
    "discipline": "Self-discipline", "negotiation": "Negotiation",
}

# industry id -> (employers, internships, certifications, scholarships,
#                universities, countries, visa, books, courses, youtube,
#                communities, alt_paths, future_skills)
_INDUSTRY_DEFAULTS: dict[str, dict] = {
 "technology-computing": dict(
    employers=["Product companies (Google, Microsoft, Zoho)", "IT services (TCS, Infosys, Wipro)", "Startups", "Global capability centres"],
    internships=["Summer internships at tech companies", "Google Summer of Code", "Startup internships via Internshala"],
    certifications=["Cloud certifications (AWS/Azure/GCP)", "Vendor certifications in your stack"],
    scholarships=["Reliance Foundation Scholarships", "Google generation scholarships", "State merit scholarships"],
    universities=["IITs & NITs", "IIITs", "BITS Pilani", "State technical universities"],
    countries=["United States", "Germany", "Canada", "Singapore", "Netherlands"], visa="moderate",
    books=["Clean Code", "The Pragmatic Programmer", "Grokking Algorithms"],
    courses=["NPTEL computer science courses", "CS50 (Harvard, free)", "Coursera specializations in your stack"],
    youtube=["freeCodeCamp", "Fireship", "NPTEL official"],
    communities=["Stack Overflow", "GitHub open source", "Local tech meetups & hackathons"],
    alt_paths=["Bootcamps + a strong project portfolio", "Open-source contributions as your CV"],
    future=["AI-assisted development", "Prompt engineering", "Cloud-native architecture"]),
 "business-finance": dict(
    employers=["Big-4 firms (Deloitte, EY, KPMG, PwC)", "Banks & NBFCs", "FMCG & conglomerates", "Consulting firms"],
    internships=["Big-4 articleship/internships", "Bank & NBFC internships", "Startup finance internships"],
    certifications=["CFA / FRM (finance tracks)", "NISM certifications", "Advanced Excel & financial modelling"],
    scholarships=["ICAI/ICSI fee concessions", "State merit scholarships", "Institute merit-cum-means awards"],
    universities=["SRCC & top Delhi University colleges", "IIMs (for MBA)", "NMIMS/Symbiosis", "Christ University"],
    countries=["United Arab Emirates", "Singapore", "United Kingdom", "United States"], visa="moderate",
    books=["Rich Dad Poor Dad (mindset)", "The Intelligent Investor", "Financial statements primers"],
    courses=["NSE/BSE certification courses", "Coursera finance specializations", "CA/CS/CMA foundation prep"],
    youtube=["CA Rachana Ranade", "Zerodha Varsity", "Finology"],
    communities=["CFA Society India", "Finance clubs & case competitions", "LinkedIn finance groups"],
    alt_paths=["Professional exams (CA/CS/CMA) without a specific degree", "Certifications + internships route"],
    future=["Data-driven decision making", "FinTech literacy", "ESG & sustainable finance"]),
 "healthcare-medicine": dict(
    employers=["Government & private hospitals", "Diagnostics chains (Dr Lal, Metropolis)", "Pharma companies", "Public health programmes"],
    internships=["Hospital internships/rotations", "NGO health programme internships", "Pharma & CRO internships"],
    certifications=["BLS/ACLS certifications", "Specialty certifications in your field"],
    scholarships=["Central Sector Scheme scholarships", "State medical education scholarships", "AIIMS/JIPMER fee structures (low)"],
    universities=["AIIMS", "CMC Vellore", "JIPMER", "State medical & nursing colleges"],
    countries=["United Kingdom (NHS)", "United Arab Emirates", "Australia", "Germany"], visa="moderate",
    books=["Anatomy & physiology foundations", "Where There Is No Doctor (community health)"],
    courses=["NEET preparation", "SWAYAM health sciences courses", "WHO OpenLearn modules"],
    youtube=["Osmosis", "Ninja Nerd", "Lecturio"],
    communities=["Medical student associations", "IMA student wings", "Public health networks"],
    alt_paths=["Allied-health diplomas with lateral growth", "Public-health masters after any life-science degree"],
    future=["Digital health & telemedicine", "AI-assisted diagnostics literacy", "Genomic medicine awareness"]),
 "engineering-manufacturing": dict(
    employers=["PSUs (BHEL, NTPC, ISRO, DRDO)", "Automotive & manufacturing majors (Tata, Mahindra, L&T)", "Core engineering consultancies", "Global R&D centres"],
    internships=["PSU summer internships", "Plant/shop-floor internships", "R&D centre internships"],
    certifications=["GATE (gateway to PSUs/M.Tech)", "Six Sigma / Lean certifications", "Software tools certifications (CAD/CAE)"],
    scholarships=["AICTE Pragati & Saksham", "State technical education scholarships", "Institute merit awards"],
    universities=["IITs & NITs", "BITS Pilani", "State engineering colleges", "IIITs (for electronics)"],
    countries=["Germany", "Japan", "United States", "South Korea"], visa="moderate",
    books=["Engineering fundamentals texts", "The Goal (operations thinking)"],
    courses=["NPTEL engineering courses", "GATE preparation", "Tool-specific courses (CAD/CAE/PLC)"],
    youtube=["NPTEL official", "Learn Engineering", "Real Engineering"],
    communities=["SAE/IEEE/ASME student chapters", "Maker spaces & robotics clubs", "GATE prep communities"],
    alt_paths=["Diploma + lateral entry to B.Tech", "ITI + apprenticeship + B.Voc ladder"],
    future=["Industry 4.0 & smart manufacturing", "Sustainability engineering", "Simulation-driven design"]),
 "science-research": dict(
    employers=["Research institutes (CSIR, TIFR, IISc)", "ISRO/DRDO/BARC", "Universities", "Corporate R&D labs"],
    internships=["IAS-SRFP summer fellowships", "Institute summer research programmes", "Lab internships via professors"],
    certifications=["CSIR-NET/GATE (for research entry)", "Domain lab-skill certifications"],
    scholarships=["INSPIRE & KVPY-legacy fellowships", "NTSE", "Institute PhD fellowships (stipended)"],
    universities=["IISc Bengaluru", "IISERs", "TIFR/NISER", "Central universities"],
    countries=["United States", "Germany", "Switzerland", "Japan"], visa="moderate",
    books=["A Brief History of Time (inspiration)", "Discipline-standard textbooks", "The Structure of Scientific Revolutions"],
    courses=["NPTEL/SWAYAM science courses", "MIT OpenCourseWare", "Summer schools in your field"],
    youtube=["Veritasium", "3Blue1Brown", "SciShow"],
    communities=["Science olympiad networks", "Institute journal clubs", "ResearchGate"],
    alt_paths=["Integrated BS-MS at IISERs", "Research assistantships after B.Sc"],
    future=["Scientific computing & data analysis", "Interdisciplinary research methods", "Science communication"]),
 "education-training": dict(
    employers=["Schools (government & private)", "EdTech companies", "Coaching institutes", "Universities & colleges"],
    internships=["Teach For India fellowship", "School teaching practice (B.Ed)", "EdTech content internships"],
    certifications=["CTET/State TET", "NET/SET (higher education)", "Instructional design certifications"],
    scholarships=["National Means-cum-Merit Scholarship", "State teacher-education scholarships"],
    universities=["Regional Institutes of Education (RIE)", "TISS", "Delhi University;Jamia (education)", "IGNOU (B.Ed)"],
    countries=["United Arab Emirates", "Singapore", "United Kingdom", "Canada"], visa="moderate",
    books=["Totto-Chan", "Pedagogy of the Oppressed", "Make It Stick (learning science)"],
    courses=["SWAYAM education courses", "Coursera learning-design courses", "TET/NET preparation"],
    youtube=["Khan Academy (as craft reference)", "Edutopia", "NCERT official"],
    communities=["Teacher communities (TeacherApp)", "Education fellowships alumni networks"],
    alt_paths=["Any degree + B.Ed", "Subject mastery + online-tutor route"],
    future=["AI-assisted personalized learning", "Learning analytics", "Hybrid classroom facilitation"]),
 "law-government": dict(
    employers=["Law firms & chambers", "Courts & tribunals", "Government departments", "Think tanks & policy orgs"],
    internships=["Court/chamber internships", "Law-firm internships", "LAMP fellowship;Think-tank internships"],
    certifications=["Bar Council enrolment", "Mediation/arbitration certifications", "Compliance certifications"],
    scholarships=["CLAT merit scholarships at NLUs", "Aditya Birla & similar merit awards"],
    universities=["National Law Universities (NLSIU, NALSAR)", "Faculty of Law DU", "Jindal Global Law School"],
    countries=["United Kingdom", "Singapore", "United Arab Emirates", "United States"], visa="high",
    books=["Constitution of India (bare act)", "Legal reasoning primers", "India After Gandhi (context)"],
    courses=["CLAT/AILET preparation", "SWAYAM law courses", "Policy bootcamps"],
    youtube=["Legal awareness channels", "Sansad TV", "Finology Legal"],
    communities=["Moot court societies", "Bar association juniors", "Policy fellowships networks"],
    alt_paths=["3-year LLB after any degree", "Company Secretary route to corporate governance"],
    future=["Technology & data-protection law", "Legal analytics literacy", "Online dispute resolution"]),
 "arts-design-media": dict(
    employers=["Design studios & agencies", "Film/OTT production houses", "Fashion & lifestyle brands", "Your own studio"],
    internships=["Studio & agency internships", "Production-house assistantships", "Portfolio apprenticeships"],
    certifications=["Software certifications (Adobe)", "Craft-specific diplomas"],
    scholarships=["NID/NIFT merit scholarships", "Cultural talent scholarships (CCRT)"],
    universities=["NID", "NIFT", "IIT IDC & design schools", "FTII/SRFTI (film)", "Sir JJ School of Art"],
    countries=["United States", "United Kingdom", "Italy", "France"], visa="high",
    books=["The Design of Everyday Things", "Steal Like an Artist", "Story (McKee, for narrative)"],
    courses=["Domestika/Skillshare craft courses", "NID/NIFT entrance prep", "YouTube masterclasses"],
    youtube=["The Futur", "Every Frame a Painting", "Proko (art)"],
    communities=["Behance/Dribbble", "Local artist collectives", "Film societies"],
    alt_paths=["Portfolio-first careers without formal degrees", "Apprenticeship under practitioners"],
    future=["AI-assisted creative workflows", "Immersive media (AR/VR)", "Personal-brand building"]),
 "communication-marketing": dict(
    employers=["Ad & media agencies", "Brands (FMCG, D2C)", "Newsrooms & digital media", "Your own audience"],
    internships=["Agency internships", "Newsroom internships", "Brand marketing internships"],
    certifications=["Google Ads & Analytics certifications", "Meta Blueprint", "HubSpot content certifications"],
    scholarships=["Journalism school merit awards", "State merit scholarships"],
    universities=["IIMC", "Symbiosis (SIMC)", "Xavier's (XIC)", "MICA (for branding)"],
    countries=["United Arab Emirates", "United Kingdom", "Singapore", "United States"], visa="moderate",
    books=["Ogilvy on Advertising", "Made to Stick", "Everybody Writes"],
    courses=["Google Digital Garage", "Content & SEO courses", "Mass-comm entrance prep"],
    youtube=["Think with Google", "Ali Abdaal (creator craft)", "Garyvee (hustle lens)"],
    communities=["Marketing meetups", "Creator communities", "Press clubs"],
    alt_paths=["Build an audience/portfolio first — degrees optional", "Certifications + freelance ladder"],
    future=["AI-assisted content production", "Marketing analytics", "Community-led growth"]),
 "agriculture-environment": dict(
    employers=["Agri-input & food companies", "FPOs & agri-startups", "Government agriculture departments", "Environmental consultancies & NGOs"],
    internships=["KVK/agri-university internships", "Agri-startup internships", "NGO field internships"],
    certifications=["Drone pilot certification (agri)", "Organic certification training", "GIS certifications"],
    scholarships=["ICAR scholarships", "State agricultural university stipends"],
    universities=["ICAR universities (IARI, GBPUAT)", "State agricultural universities", "TERI SAS (environment)"],
    countries=["Netherlands", "Australia", "Israel", "New Zealand"], visa="moderate",
    books=["The Omnivore's Dilemma", "Agronomy handbooks", "Silent Spring (environment classic)"],
    courses=["ICAR e-courses", "NPTEL environmental science", "Agri-business courses"],
    youtube=["Discover Agriculture", "Down To Earth", "Agri-university channels"],
    communities=["FPO networks", "Young farmer forums", "Environmental youth networks"],
    alt_paths=["Diploma in agriculture + field experience", "Family-farm innovation + agripreneurship"],
    future=["Precision & digital agriculture", "Climate-smart practices", "Agri value-chain finance"]),
 "construction-urban": dict(
    employers=["Construction majors (L&T, Tata Projects)", "Architecture & design consultancies", "Real-estate developers", "Smart-city SPVs & ULBs"],
    internships=["Site internships", "Architecture firm internships", "Urban local body internships"],
    certifications=["RICS pathways", "LEED/IGBC green building", "Primavera/MS Project"],
    scholarships=["AICTE scholarships", "CoA/ITPI merit awards"],
    universities=["SPA Delhi", "IITs (Civil/Planning)", "CEPT Ahmedabad", "NICMAR (construction management)"],
    countries=["United Arab Emirates", "Saudi Arabia", "Singapore", "Australia"], visa="low",
    books=["101 Things I Learned in Architecture School", "The Death and Life of Great American Cities"],
    courses=["NPTEL civil & planning courses", "BIM tool courses", "NATA/JEE B.Arch prep"],
    youtube=["The B1M", "Dami Lee (architecture)", "NPTEL"],
    communities=["Student chapters (ASCE, NASA India - architecture)", "Urbanist forums"],
    alt_paths=["Diploma + site experience ladder", "Draftsperson → BIM modeller ladder"],
    future=["BIM & digital construction", "Green building", "Modular & prefab methods"]),
 "hospitality-tourism": dict(
    employers=["Hotel chains (Taj, Oberoi, Marriott)", "Airlines & cruise lines", "Event companies", "Your own venture"],
    internships=["Hotel industrial training (IHM)", "Event crew roles", "Travel company internships"],
    certifications=["IATA travel certifications", "Food safety (FSSAI/FoSTaC)", "Sommelier/barista certifications"],
    scholarships=["NCHM merit scholarships", "State hospitality institute awards"],
    universities=["IHMs (via NCHM JEE)", "WGSHA Manipal", "Christ (tourism)", "IITTM"],
    countries=["United Arab Emirates", "Switzerland", "Maldives", "Singapore", "Cruise lines worldwide"], visa="low",
    books=["Setting the Table (Danny Meyer)", "Hospitality operations texts"],
    courses=["NCHM JEE prep", "Hotel-school MOOCs", "Barista/bakery workshops"],
    youtube=["Hotel management channels", "Chef channels (Ranveer Brar, Sanjyot Keer)"],
    communities=["Hospitality student forums", "Chef communities", "Travel-trade associations"],
    alt_paths=["Skill diplomas + on-floor experience ladder", "Cruise/Gulf placements after training"],
    future=["Revenue analytics", "Experience design", "Sustainable tourism"]),
 "transport-logistics": dict(
    employers=["E-commerce & 3PL (Delhivery, DHL)", "Airlines & airports", "Shipping lines & ports", "Indian Railways & metros"],
    internships=["Warehouse & hub internships", "Port/airline operations internships", "Supply-chain analyst internships"],
    certifications=["IATA/FIATA logistics certifications", "Six Sigma", "DGCA licenses (flying/drones)"],
    scholarships=["Maritime training sponsorships", "Airline cadet programmes (self-funded mostly)"],
    universities=["Indian Maritime University", "IIFT (trade)", "NITIE/IIMs (SCM)", "Flying schools (DGCA approved)"],
    countries=["United Arab Emirates", "Singapore", "Netherlands", "Ships & global routes"], visa="low",
    books=["The Box (container shipping history)", "Supply chain management texts"],
    courses=["NPTEL supply chain courses", "IATA foundation courses", "EXIM/customs courses"],
    youtube=["Wendover Productions (logistics)", "Maritime channels"],
    communities=["Supply-chain professional bodies (CSCMP)", "Maritime unions & alumni", "Aviation forums"],
    alt_paths=["Operations floor → manager ladder", "Merchant navy ratings → officer ladder"],
    future=["Supply-chain analytics", "Automation & robotics in warehouses", "Green logistics"]),
 "sports-wellness": dict(
    employers=["Franchises & leagues (IPL, ISL)", "Academies & schools", "Gyms & wellness brands", "Sports Authority of India"],
    internships=["Academy assistant-coach roles", "Franchise season internships", "Gym floor internships"],
    certifications=["NIS coaching diplomas", "ACE/ACSM/K11 fitness certifications", "Yoga Certification Board levels"],
    scholarships=["Sports Authority of India schemes", "Khelo India scholarships", "Sports quota admissions"],
    universities=["NIS Patiala", "LNIPE Gwalior", "TNPESU", "Symbiosis (sports management)"],
    countries=["United Arab Emirates", "Australia", "United Kingdom", "United States"], visa="moderate",
    books=["Legacy (culture)", "Peak (expertise science)", "Anatomy for athletes"],
    courses=["NIS/B.P.Ed programmes", "Sports-science MOOCs", "Fitness certification prep"],
    youtube=["Athlean-X (fitness science)", "GCN/sport-specific channels", "Yoga With Adriene"],
    communities=["Coaching associations", "Fitness professional networks", "Esports Discords"],
    alt_paths=["Playing career → coaching ladder", "Certification-first fitness careers"],
    future=["Sports data analysis", "Injury-prevention science", "Online coaching business"]),
 "social-impact": dict(
    employers=["NGOs & foundations (Pratham, Akshaya Patra)", "CSR teams", "Hospitals & clinics (psychology)", "Multilateral agencies (UNICEF)"],
    internships=["NGO field internships", "Fellowships (Gandhi, SBI Youth)", "Hospital psychology internships"],
    certifications=["RCI licensure (clinical paths)", "M&E certifications", "Counselling skill certifications"],
    scholarships=["TISS/APU financial aid", "Fellowships with stipends (Teach For India)"],
    universities=["TISS", "Azim Premji University", "Delhi School of Social Work", "Christ (psychology)"],
    countries=["United Kingdom", "Netherlands", "Kenya (development hubs)", "United States"], visa="high",
    books=["Poor Economics", "Man's Search for Meaning", "Counselling skills primers"],
    courses=["SWAYAM psychology & social work", "Coursera public health & M&E", "RCI-approved programmes"],
    youtube=["Psych2Go (starting point)", "Development-sector talks", "TISS lectures"],
    communities=["Development-sector networks (DevNetJobs)", "Psychology student associations", "Fellowship alumni"],
    alt_paths=["Any degree + MSW", "Fellowship-first careers"],
    future=["Data-driven programme design", "Digital mental-health delivery", "Impact measurement"]),
 "defence-security": dict(
    employers=["Indian Armed Forces", "CAPFs & state police", "DRDO & defence PSUs", "Corporate security firms"],
    internships=["NCC (the best preparation)", "Police citizen-cadet programmes", "Defence-tech startup internships"],
    certifications=["NCC A/B/C certificates", "NEBOSH/fire-safety (civil side)", "Cyber-defence certifications"],
    scholarships=["Sainik & military school routes", "NDA (free training + stipend)", "Defence quota benefits"],
    universities=["NDA Khadakwasla", "Sainik Schools & RIMC", "National Forensic Sciences University", "Defence-tech institutes"],
    countries=["Serve in India (UN peacekeeping deputations exist)"], visa="high",
    books=["Param Vir (biographies)", "India's Most Fearless", "Service-exam preparation guides"],
    courses=["NDA/CDS/AFCAT preparation", "SSB interview preparation", "Fire & safety diplomas"],
    youtube=["SSB preparation channels", "Defence aspirant channels", "Armed forces official channels"],
    communities=["NCC networks", "Defence-aspirant forums", "Veteran mentorship groups"],
    alt_paths=["Agniveer entry + service ladder", "Technical entries after engineering"],
    future=["Cyber & information warfare literacy", "Drone & unmanned systems", "Crisis leadership"]),
}

_ENV_RULES = (
    (("sea", "ports"), "Ships, ports and coastal facilities — a life around water"),
    (("outdoors", "field", "farming", "forests", "wildlife", "adventure"), "Field-first: outdoors, on sites and in communities more than at a desk"),
    (("site", "construction", "infrastructure"), "Project sites and offices — boots and drawings in the same week"),
    (("lab", "research", "science"), "Laboratories and research facilities with focused desk analysis"),
    (("hospital", "care", "health", "rehab"), "Hospitals, clinics and care settings — human contact all day"),
    (("kitchen", "cooking", "baking"), "Professional kitchens — hot, fast and team-driven"),
    (("studio", "design", "art", "music", "performance"), "Studios and creative spaces, with deadline crunches"),
    (("classroom", "teaching", "children", "school"), "Classrooms and learning spaces"),
    (("events", "weddings", "conferences"), "Venues and event floors — evenings and weekends included"),
    (("courtroom", "law-enforcement", "justice"), "Courts, chambers and field postings"),
)


def _work_environment(tags: str, remote: float) -> str:
    tag_set = set(tags.split())
    for keys, desc in _ENV_RULES:
        if tag_set & set(keys):
            return desc
    if remote >= 0.8:
        return "Office or fully remote — laptop work with flexible location"
    if remote >= 0.4:
        return "Office-based with meaningful remote flexibility"
    return "Primarily on-site — offices, facilities or the field depending on the role"


def _problem_style(tags: str) -> str:
    t = set(tags.split())
    if t & {"analytical", "logic", "mathematics", "numbers", "research", "data"}:
        return "Analytical — decompose, measure, model, verify"
    if t & {"creative", "design", "storytelling", "art", "music"}:
        return "Creative — explore, prototype, iterate on ideas"
    if t & {"people", "empathy", "communication", "service", "care", "teaching"}:
        return "People-centred — listen, mediate, guide and align humans"
    if t & {"hands-on", "practical", "machines", "building", "operations"}:
        return "Practical — diagnose, build, fix and improve on the ground"
    return "Adaptive — mix analysis, action and people skills as the situation demands"


def _learning_style(tags: str) -> str:
    t = set(tags.split())
    if t & {"analytical", "mathematics", "logic", "research"}:
        return "analytical"
    if t & {"creative", "design", "curious", "storytelling"}:
        return "exploratory"
    if t & {"people", "teaching", "communication", "service"}:
        return "collaborative"
    if t & {"hands-on", "practical", "machines", "building", "fitness", "sports"}:
        return "practical"
    return "reflective"


def _band(x: float, bands: tuple[str, ...]) -> str:
    return bands[min(len(bands) - 1, int(x * len(bands)))]


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.split(";") if x.strip()]


# ---------------------------------------------------------------------------
# Expansion: catalog entry -> full canonical profile dict
# ---------------------------------------------------------------------------

def expand(entry: tuple, industry_id: str, industry_name: str, known: set[str]) -> dict:
    (name, family, tags, summary, subjects, degrees, skills, tech,
     sal_lo, sal_hi, difficulty, competition, demand, autom, remote,
     cities, related) = entry
    d = _INDUSTRY_DEFAULTS[industry_id]
    tag_list = tags.split()
    skills_l, tech_l = _split(skills), _split(tech)
    cities_l = _split(cities)
    related_known = [r for r in _split(related) if r in known and r != name]

    traits = [v for k, v in _TAG_TRAITS.items() if k in tag_list][:5] or ["Motivated", "Adaptable"]
    who_for = [v for k, v in _TAG_WHO_FOR.items() if k in tag_list][:3]
    if not who_for:
        who_for = [f"You are drawn to {family.lower()} and want a broad path you can shape"]
    who_avoid = []
    if difficulty >= 4:
        who_avoid.append("You want a short, easy study path — this one demands years of serious preparation")
    if competition >= 4:
        who_avoid.append("Intense competition drains you — entry here is a contest")
    if remote <= 0.2:
        who_avoid.append("You want a laptop-anywhere lifestyle — this work happens in person")
    if autom >= 0.45:
        who_avoid.append("You want to avoid routine tasks — parts of this role are being automated, so you must keep climbing the skill ladder")
    if not who_avoid:
        who_avoid = ["You strongly prefer solitary desk work over this field's day-to-day reality"]

    soft = [v for k, v in _SOFT_SKILL_TAGS.items() if k in tag_list][:4] or ["Communication", "Teamwork"]
    daily = [
        f"Apply {skills_l[0].lower()} to real problems",
        f"Collaborate with your team using {skills_l[1].lower() if len(skills_l) > 1 else 'core professional skills'}",
        f"Keep improving at {skills_l[2].lower() if len(skills_l) > 2 else 'the craft'} — the field keeps moving",
        "Communicate progress, results and decisions to the people who depend on them",
    ]

    demand_band = _band(demand, ("limited", "steady", "strong", "booming"))
    ai_band = _band(autom, ("minimal — deeply human/physical work", "low — AI assists rather than replaces",
                            "moderate — routine parts will be automated; the judgement stays human",
                            "high — the role is being reshaped; continuous upskilling is essential"))
    advantages = []
    if demand >= 0.8:
        advantages.append(f"Demand is {demand_band}: opportunities across India and beyond")
    if remote >= 0.7:
        advantages.append("High remote and location flexibility")
    if sal_hi >= 40:
        advantages.append(f"Strong earning ceiling (₹{sal_hi} LPA+ at senior levels)")
    if autom <= 0.2:
        advantages.append("Highly resilient to AI automation")
    advantages.append(f"A broad {family} foundation that opens multiple specializations later")
    challenges = []
    if competition >= 4:
        challenges.append("Fierce competition for the best seats and roles")
    if difficulty >= 4:
        challenges.append("A long, demanding preparation and learning curve")
    if autom >= 0.4:
        challenges.append("Routine tasks are being automated — you must keep moving up the value chain")
    if remote <= 0.2:
        challenges.append("Location-bound work; postings and relocation are part of the deal")
    challenges.append("Early years demand patience before the rewards compound")

    gov = 0.9 if {"service", "nation", "law-enforcement", "defence", "railways"} & set(tag_list) else (
        0.7 if industry_id in ("law-government", "defence-security", "education-training", "healthcare-medicine") else 0.4)
    ent = 0.9 if "entrepreneurship" in tag_list or sal_lo == 0 else (
        0.7 if remote >= 0.7 or "creative" in tag_list else 0.45)
    freelance = round(min(1.0, remote * 0.7 + (0.25 if {"creative", "writing", "design", "coaching"} & set(tag_list) else 0.05)), 2)

    smaller = ("Viable in smaller cities — demand exists well beyond the metros."
               if demand >= 0.75 and remote < 0.6 else
               "Remote-friendly: smaller-city living with metro-level work is realistic."
               if remote >= 0.6 else
               "Concentrated in bigger hubs today; smaller-city presence is growing slowly.")
    rural = ("Real rural relevance — this field serves or operates in rural India directly."
             if industry_id in ("agriculture-environment", "healthcare-medicine", "education-training") or "rural" in tag_list else
             "Limited rural presence; expect to base yourself in a town or city.")

    faqs = [
        [f"What does {name} pay in India?",
         f"Entry roles typically start around ₹{sal_lo} LPA and senior professionals reach ₹{sal_hi} LPA or more. "
         "Live, region-specific salary data is retrieved by the platform when you ask."],
        ["What should I study after Class 12?",
         f"Focus on {', '.join(_split(subjects)[:2])}. Typical degrees: {', '.join(_split(degrees)[:2])}. "
         f"Alternatives exist: {d['alt_paths'][0].lower()}."],
        ["Will AI take over this career?",
         f"AI impact is {ai_band}. Broad paths like {name} evolve rather than disappear — "
         "the students who pair domain skill with AI tools benefit most."],
        ["Is this a broad path or a specific job?",
         f"{name} is a career direction. Once inside it you can specialize further — "
         "the platform will map specializations in future versions."],
    ]

    return {
        "id": slugify(name), "name": name, "industry": industry_id,
        "career_family": family, "tags": tag_list,
        "student_summary": summary,
        "overview": (f"{summary} {name} sits in the {family} family of {industry_name}. "
                     f"It is a broad career direction — you can enter it through several routes and "
                     f"specialize later without restarting."),
        "who_is_this_for": who_for, "who_should_avoid": who_avoid,
        "daily_responsibilities": daily,
        "work_environment": _work_environment(tags, remote),
        "problem_solving_style": _problem_style(tags),
        "school_subjects": _split(subjects), "college_degrees": _split(degrees),
        "alternative_paths": d["alt_paths"],
        "core_skills": skills_l, "soft_skills": soft,
        "technical_skills": tech_l,
        "future_skills": d["future"],
        "tools": tech_l[:3] or ["Standard professional tools"],
        "technologies": tech_l,
        "personality_traits": traits, "learning_style": _learning_style(tags),
        "difficulty": difficulty, "competition_level": competition,
        "career_progression": [
            ["Student / trainee", "years 0-2"],
            [f"Working professional in {family.lower()}", "years 2-5"],
            ["Senior professional / specialist", "years 5-10"],
            ["Leader, expert or independent practice", "years 10+"],
        ],
        "typical_employers": d["employers"],
        "entrepreneurship": round(ent, 2), "government_opportunities": round(gov, 2),
        "remote_work": remote, "freelancing": freelance,
        "salary_currency": "₹", "salary_entry_lpa": sal_lo, "salary_senior_lpa": sal_hi,
        "scope": f"Demand outlook in India is {demand_band}; see FAQs for how the platform keeps this current.",
        "future_demand": demand, "growth": round(min(1.0, demand * 0.9 + 0.05), 2),
        "ai_impact": ai_band, "automation_risk": autom,
        "advantages": advantages[:4], "challenges": challenges[:4],
        "misconceptions": [
            f"“You must pick your exact job title now.” {name} is a direction — specialization comes later.",
            "“Only toppers make it.” Consistent skill-building beats one exam rank in the long run.",
        ],
        "portfolio_ideas": [f"A project demonstrating {skills_l[0].lower()}",
                            f"A documented case study of {(skills_l[1].lower() if len(skills_l) > 1 else 'your best work')}"],
        "projects": [f"Beginner: explore {skills_l[0].lower()} with a small self-chosen project",
                     f"Intermediate: build or run something real using {tech_l[0] if tech_l else 'the field-standard tools'}"],
        "internships": d["internships"], "certifications": d["certifications"],
        "scholarships": d["scholarships"], "universities": d["universities"],
        "books": d["books"], "courses": d["courses"], "youtube": d["youtube"],
        "communities": d["communities"],
        "major_hiring_cities": cities_l, "relocation_cities": cities_l[:3],
        "smaller_city_scope": smaller, "rural_scope": rural,
        "home_state_note": ("Ask the AI coach about your state — regional demand, cities and "
                            "relocation advice are generated live from retrieved data, never hardcoded."),
        "top_countries": d["countries"],
        "language_requirements": ["English"] + (["Local language for client/patient-facing roles"]
                                                if industry_id in ("healthcare-medicine", "law-government",
                                                                   "social-impact", "education-training") else []),
        "visa_difficulty": d["visa"],
        "transition_paths": [f"Toward {r}: build the shared skills and take a bridging project or course"
                             for r in related_known] or [f"Deepen within {family} toward senior and specialist roles"],
        "related_careers": related_known,
        "faqs": faqs,
        "confidence": 0.75,
        "sources": ["detective-monkey:career-catalog:v1", "detective-monkey:generator:v1"],
        "schema_version": SCHEMA_VERSION, "version": 1,
    }


# ---------------------------------------------------------------------------
# Optional LLM enrichment (structured JSON prompt; validated before accept)
# ---------------------------------------------------------------------------

_LLM_FIELDS = ("student_summary", "overview", "who_is_this_for", "who_should_avoid",
               "daily_responsibilities", "advantages", "challenges", "misconceptions")


def llm_enrich(profile: dict) -> dict:
    """Regenerate narrative fields via Gemini; falls back silently without a key."""
    import os
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return profile
    from detective_monkey.infrastructure.providers import GeminiProvider

    class _Prompt:
        system_prompt = (
            "You generate career-guidance content for Indian students under 18. "
            "Return ONLY a JSON object with exactly these keys: "
            + ", ".join(_LLM_FIELDS)
            + ". String fields stay strings; list fields stay lists of short strings. "
              "Be factual, encouraging and specific to the career. No markdown.")
        user_question = f"Career: {profile['name']} ({profile['career_family']}, {profile['industry']})"
        sections = ()

    reply = GeminiProvider(key).generate(_Prompt())
    start, end = reply.find("{"), reply.rfind("}")
    if start == -1 or end <= start:
        return profile
    try:
        data = json.loads(reply[start:end + 1])
    except json.JSONDecodeError:
        return profile
    updated = dict(profile)
    for field in _LLM_FIELDS:
        value = data.get(field)
        if isinstance(profile[field], list):
            if isinstance(value, list) and value and all(isinstance(x, str) and x.strip() for x in value):
                updated[field] = value[:5]
        elif isinstance(value, str) and 30 <= len(value) <= 1500:
            updated[field] = value.strip()
    updated["sources"] = profile["sources"] + ["llm:gemini-structured:v1"]
    return updated if not validate_career_json(updated) else profile


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    check_only = "--check" in sys.argv
    use_llm = "--llm" in sys.argv

    known = {e[0] for _, (_, _, _, careers) in INDUSTRIES.items() for e in careers}
    profiles: list[dict] = []
    problems: list[str] = []
    industries_out = []

    for industry_id, (industry_name, icon, description, careers) in INDUSTRIES.items():
        for entry in careers:
            profile = expand(entry, industry_id, industry_name, known)
            if use_llm:
                profile = llm_enrich(profile)
            issues = validate_career_json(profile)
            if not profile["related_careers"]:
                issues.append("related_careers empty after integrity filtering")
            unknown = [r for r in _split(entry[16]) if r not in known]
            if unknown:
                problems.append(f"[warn] {profile['name']}: unknown related {unknown}")
            if issues:
                problems.append(f"[ERROR] {profile['name']}: {issues}")
            else:
                profiles.append(profile)

        by_demand = sorted(careers, key=lambda e: -e[12])
        industries_out.append({
            "id": industry_id, "name": industry_name, "icon": icon,
            "description": description,
            "career_count": len(careers),
            "featured_careers": [slugify(e[0]) for e in careers[:3]],
            "trending_careers": [slugify(e[0]) for e in by_demand[:3]],
            "future_note": "New specializations will appear inside these career paths in future versions.",
        })

    seen: set[str] = set()
    for profile in profiles:
        if profile["id"] in seen:
            problems.append(f"[ERROR] duplicate career id {profile['id']}")
        seen.add(profile["id"])

    for line in problems:
        print(line)
    errors = [p for p in problems if p.startswith("[ERROR]")]
    print(f"\n{len(profiles)} valid profiles across {len(industries_out)} industries; "
          f"{len(errors)} errors, {len(problems) - len(errors)} warnings.")
    if errors:
        return 1
    if check_only:
        return 0

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for old in DATA_DIR.glob("*.json"):
        old.unlink()
    for profile in profiles:
        path = DATA_DIR / f"{profile['id'].replace('-', '_')}.json"
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA_DIR / "industries.json").write_text(
        json.dumps(industries_out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(profiles)} career files + industries.json to {DATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
