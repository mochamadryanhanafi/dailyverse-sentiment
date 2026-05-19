import re

def tokenize(text: str) -> set[str]:
    return set(re.findall(r'\w+', text.lower()))

def jaccard(s1: set[str], s2: set[str]) -> float:
    u = len(s1 | s2)
    return len(s1 & s2) / u if u else 0.0

sentences = ["Jokowi meresmikan jalan tol.", "Presiden Jokowi meresmikan jalan tol baru.", "Harga BBM naik hari ini."]
accepted = []
for s in sentences:
    toks = tokenize(s)
    is_dup = False
    for acc_s, acc_toks in accepted:
        if jaccard(toks, acc_toks) >= 0.7:
            is_dup = True
            break
    if not is_dup:
        accepted.append((s, toks))

print([a[0] for a in accepted])
