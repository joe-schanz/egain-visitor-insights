"""Network-type rules: who owns the IP, and can a company be inferred from it?

net_type values
  egain           eGain's own offices/VPN: exclude (employees, not prospects)
  security_proxy  enterprise secure-web-gateway (Zscaler, Netskope ...): a real corporate user,
                  but the proxy hides which company
  hosting         cloud / datacenter / VPN / proxy farm: almost always automation or anonymised
  isp             consumer or small-business internet provider: company unknown unless the
                  registry (RDAP) shows the block is assigned to a named customer
  organization    the IP block is owned by a named organisation (bank, insurer, agency, university ...)
  unverified      not matched by any rule above (shown with low confidence)

Rules are plain regex lists so each verdict can be explained. Patterns are matched against
"<as_name> <as_domain>" in lower case.
"""
from __future__ import annotations

import re

EGAIN = r"\begain\b|egain\.com"

SECURITY_PROXY = r"zscaler|netskope|forcepoint|opendns|cisco umbrella|palo alto|iboss|mcafee|menlo security|cato networks|proofpoint|mimecast"

# Named providers: checked BEFORE the organisation rule (e.g. "Hurricane Electric" is a backbone,
# not a utility).
HOSTING_NAMED = (
    # hyperscalers & CDNs & crawler operators
    r"amazon|google|microsoft|alibaba|tencent|huawei|oracle|ibm cloud|akamai|cloudflare|fastly|byteplus|"
    r"baidu|facebook|meta networks|proton ag|wowrack|angelnet|trafficforce|code200|1337 services|dzcrd|"
    r"getechbrothers|powerhouse management|blix solutions|novoserve|gnet llc|bitdefender|"
    r"hurricane electric|"
    # named hosting / proxy / VPN providers seen in this log
    r"m247|leaseweb|ovh|vultr|constant company|digitalocean|hetzner|linode|latitude|packetexchange|quickpacket|"
    r"purevoltage|sprious|wstelecom|larus|my-tec|3xk|limestone|performive|hivelocity|renewablefreedom|"
    r"fns-holdings|global transit|wiit|contabo|choopa|ionos|scaleway|zenlayer|psychz|cdn77|datapacket|"
    r"g-core|gcore|stark industries|aeza|frantech|buyvm|clouvider|ipxo|godaddy|selectel|netcup|ipvolume|"
    r"todaslasredes|web2objects|h4y|dynanode|delska|route ?95|tzulo|packethub|hyonix|elitework|terratransit|"
    r"syn\.one|transitx|core-backbone|cyberology|ddps|think huge|applied-privacy|f3netze|datawagon|tier\.net|"
    r"i3d|ib\.systems|31173|melbicom|quality-network|nearoute|adoard|propersupport|globalsecurelayer|udasha|"
    r"realitymedia|wenium|handy networks|solucionesfavorables|laceibanetsociety|transoceanet|fxdana|velia|"
    r"ctrls|o2switch|ecritel|netenterprise|ringsquared|stemconnect|microlinknet|limericktechnologies|"
    r"central ?technology|sengked|nj-ix|intel-port|aktekbilisim|dimensione|"
    # residential-proxy / VPN resellers found as RDAP registrants (rent IPs on ISP networks)
    r"blazing seo|biterika|big sky services|osolabs|hop bilisim|direct impression|segna tech|inet ltd|"
    r"ipnetzone|windscribe|power nms|pitline|lowping|primeworld digital|global telemanagement|we data|"
    r"terraserv|hosted backbone|halo colocation|"
    # transit backbones (traffic from these is infrastructure, not an end customer)
    r"cogent|gtt\.net|zayo|tata comm|telia carrier|arelion|ntt america|allstream"
)
HOSTING_GENERIC = r"host|cloud|server|data ?cent|datacamp|colo|vps|dedicated|vpn|proxy|seo\b"

ISP = (
    r"tele|telco|telekom|communications|comcast|charter|verizon|at&t|att\.com|cox\b|jio|airtel|bt\.net|"
    r"virgin|sky\b|orange|t-mobile|vodafone|spacex|starlink|broadband|cable|mobile|wireless|fiber|fibre|"
    r"internet|telefonica|movistar|claro|swisscom|proximus|kpn|ziggo|rogers|shaw|telus|optus|chinanet|"
    r"china unicom|china mobile|pldt|globe|mtn|safaricom|rostelecom|megafon|beeline|turk|etisalat|ooredoo|"
    r"elisa|telenor|telia|a1 |magyar|liberty|frontier|windstream|centurylink|lumen|level 3|altice|optimum|"
    r"spectrum|mediacom|astound|sonic|rcn|earthlink|bite|yemen|scancom|reliance|bsnl|act fibernet|hathway|"
    r"excitel|tpg|iinet|vocus|aussie|spark|vivo|digi|iliad|sfr|bouygues|fastweb|ptcl|viettel|vnpt|indosat|"
    r"telkom|maxis|singtel|starhub|hkt|pccw|hkbn|chunghwa|cht\.com|kddi|softbank|docomo|lguplus|lg dacom|"
    r"sk broad|superonline|netia|plusnet|1und1|versatel|play\.pl|converge|leaptel|bevcomm|multi\.net|"
    r"videotron|sunrise|cellcom|tm\.com\.my|tdc|eir\.ie|dna\.fi|bahnhof|ewe|drei\.at|teracom|netcom-bw|"
    r"bluwifi|samruddhi|wave broadband|cable onda|sky uk|deutsche telekom|wow!|frontiernet|bell canada|"
    r"belwue|dfn\.de|jisc|aveniq|xenox|intercom online|amx argentina|vmedia|special communication|transit as|ecuanet|tt dotcom|metronet|teljet"
)

# Strong signals that an AS / registry name is an end-user organisation, not a network provider.
ORGANIZATION = (
    r"\bbank|bancorp|banco|banca|bankasi|\binsurance|assurance|financial|credit union|securities|\bcapital\b|"
    r"health|hospital|medical|clinic|pharma|blue cross|blue shield|kaiser|"
    r"universit|college|school|academy|"
    r"government|ministry|department of|state of|county of|city of|federal|revenue service|\.gov\b|"
    r"energy|electric|petrol|oil\b|gas\b|utility|"
    r"airline|airways|motors|automotive|logistics|railway|"
    r"jpmorgan|chase|sberbank|worldpay|vantiv|cisco|check point|lg cns|siac|moex|duke"
)

_RX = {k: re.compile(v) for k, v in {
    "egain": EGAIN, "security_proxy": SECURITY_PROXY, "hosting_named": HOSTING_NAMED,
    "organization": ORGANIZATION, "hosting_generic": HOSTING_GENERIC, "isp": ISP}.items()}

# Words that mean an RDAP registrant is the network provider itself, not a customer.
PROVIDER_WORDS = re.compile(
    r"communications|telecom|telekom|cable|broadband|internet|network|wireless|isp\b|comcast|charter|"
    r"verizon|at&t|cox|spectrum|lumen|centurylink|level 3|frontier|windstream|cogent|zayo|hosting|"
    r"cloud|datacenter|data center|mobile|fiber|fibre|ip services|transit|telephone|tele\b|sympatico|\bhse\b|residential|customer|subscriber", re.I)


def classify_asn(as_name: str, as_domain: str) -> str:
    s = f"{as_name} {as_domain}".lower()
    if not s.strip():
        return "unverified"
    # order matters: our own offices, security proxies, named hosting/backbone providers,
    # then organisation names (so "Bank X Network" still counts), then generic hosting words, then ISPs.
    for label in ["egain", "security_proxy", "hosting_named", "organization", "hosting_generic", "isp"]:
        if _RX[label].search(s):
            return label.replace("_named", "").replace("_generic", "")
    return "unverified"
