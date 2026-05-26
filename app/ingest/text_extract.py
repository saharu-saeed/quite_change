"""Extract qualitative (定性情報) text blocks from an EDINET XBRL zip."""
from __future__ import annotations
import re
import zipfile
from pathlib import Path
from lxml import etree

# Tags that typically hold qualitative MD&A / business-results narrative.
# Listed in priority order; first match wins. EDINET tag names drift between
# fiscal years, so we keep multiple fallbacks.
QUALITATIVE_TAGS = (
    "BusinessResultsOfGroupTextBlock",
    "OverviewOfBusinessResultsTextBlock",
    "OperatingResultsTextBlock",
    "ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock",
    "BusinessPolicyBusinessEnvironmentIssuesToAddressEtcTextBlock",
)


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_qualitative_text(zip_path: Path) -> tuple[str, str]:
    """Return (text, matched_tag_name). Empty string if no tag matched."""
    with zipfile.ZipFile(zip_path) as zf:
        xbrl_names = [n for n in zf.namelist() if n.lower().endswith((".xbrl", ".htm", ".html"))]
        # Prefer PublicDoc xbrl files
        xbrl_names.sort(key=lambda n: (0 if "PublicDoc" in n else 1, 0 if n.endswith(".xbrl") else 1))
        for name in xbrl_names:
            data = zf.read(name)
            try:
                root = etree.fromstring(data, parser=etree.XMLParser(recover=True, huge_tree=True))
            except Exception:
                continue
            if root is None:
                continue
            for tag in QUALITATIVE_TAGS:
                # Match on local-name() — namespaces shift year over year.
                nodes = root.xpath(f"//*[local-name()='{tag}']")
                if nodes and nodes[0].text:
                    text = _strip_html("".join(nodes[0].itertext()))
                    if len(text) > 200:
                        return text, tag
    return "", ""
