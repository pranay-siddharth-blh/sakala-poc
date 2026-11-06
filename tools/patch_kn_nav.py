"""22 Oct 2026 (Pranay): navigation by voice in Kannada behaves exactly like English.
Found on the real live voice: 'citizen view ಗೆ ಕರ್ಕೊಂಡು ಹೋಗಿ' made the model ask for the APP view of the citizen desk (it read
'view' as web/app), so the phone overlay opened and the desk stayed on the Chief Secretary.
- go_to: a web / app switch only when the person's own words mention web / website / app / mobile / phone (English or Kannada);
  otherwise 'X view' is a profile switch. Kannada profile words (ನಾಗರಿಕ, ಅಧಿಕಾರಿ, ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿ) and navigation verbs
  (ವಾಪಸ್, ಹಿಂದೆ, ಹೋಗಿ, ಕರ್ಕೊಂಡು, ತೋರಿಸಿ, ಮುಚ್ಚಿ) are understood.
- the rules brain (fallback / fake Live): the same Kannada navigation -> switch_profile / go_to dashboard / inbox / web-app views."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(rel, pairs):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:140]}"
        s = s.replace(old, new, 1)
    ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


patch("mitra/server/tools.py", [
    ('''    w = ((args.get("target") or "") + " " + (args.get("_text") or "")).lower()
    p = sess["profile"]
    view = "web" if re.search(r"\\b(web|website|desktop|browser|laptop|big screen|full screen)\\b", w) else \\
        "app" if re.search(r"\\b(app|mobile|phone)\\b", w) and not re.search(r"\\b(apply|application|whatsapp)\\b", w) else ""
    if view:
        to = "cs" if re.search(r"chief|secretary|\\bcs\\b|madam", w) else "officer" if re.search(r"\\bofficer|tahsildar|\\bpdo\\b", w) else \\
            "citizen" if re.search(r"\\bcitizen", w) else p''',
     '''    w = ((args.get("target") or "") + " " + (args.get("_text") or "")).lower()
    w = (w.replace("ನಾಗರಿಕ", " citizen ").replace("ಸಿಟಿಜನ್", " citizen ").replace("ಅಧಿಕಾರಿ", " officer ").replace("ಆಫೀಸರ್", " officer ")
          .replace("ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿ", " chief secretary ").replace("ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", " dashboard ").replace("ಡ್ಯಾಶ್ಬೋರ್ಡ್", " dashboard ")
          .replace("ಆ್ಯಪ್", " app ").replace("ಆಪ್", " app ").replace("ಮೊಬೈಲ್", " mobile ").replace("ಫೋನ್", " phone ").replace("ವೆಬ್", " web "))
    p = sess["profile"]
    said0 = (args.get("_text") or "").lower()
    VIEW_WORDS = r"\\b(web|website|desktop|browser|laptop|big screen|full screen|app|mobile|phone)\\b|ವೆಬ್|ಆ್ಯಪ್|ಆಪ್|ಮೊಬೈಲ್|ಫೋನ್|ಕಂಪ್ಯೂಟರ್"
    view = "web" if re.search(r"\\b(web|website|desktop|browser|laptop|big screen|full screen)\\b", w) else \\
        "app" if re.search(r"\\b(app|mobile|phone)\\b", w) and not re.search(r"\\b(apply|application|whatsapp)\\b", w) else ""
    if view and said0 and not re.search(VIEW_WORDS, said0):
        view = ""                                       # 'citizen view' is a profile, unless the person said web / app / phone themselves
    if view:
        to = "cs" if re.search(r"chief|secretary|\\bcs\\b|madam", w) else "officer" if re.search(r"\\bofficer|tahsildar|\\bpdo\\b", w) else \\
            "citizen" if re.search(r"\\bcitizen", w) else p'''),
    ('''    said = (args.get("_text") or "").lower()
    if said and not re.search(r"dashboard|main screen|main view|main page|home|chart|graph|visual|picture|\\bmap\\b|inbox|citizen|officer|"
                              r"chief|secretary|screen|close|back|dismiss|exit|leave|go to|take me|return", said):''',
     '''    said = (args.get("_text") or "").lower()
    if said and not re.search(r"dashboard|main screen|main view|main page|home|chart|graph|visual|picture|\\bmap\\b|inbox|citizen|officer|"
                              r"chief|secretary|screen|close|back|dismiss|exit|leave|go to|take me|return|view|profile|"
                              r"ವಾಪಸ್|ಹಿಂದೆ|ಹೋಗಿ|ಕರ್ಕೊಂಡು|ಕರೆದುಕೊಂಡು|ತೋರಿಸಿ|ಮುಚ್ಚಿ|ತೆರೆಯಿರಿ|ತೆಗೆ|ನಾಗರಿಕ|ಅಧಿಕಾರಿ|ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿ|ಡ್ಯಾಶ್", said):'''),
])

patch("mitra/server/brain.py", [
    ('''    m = re.search(r"\\b(switch|change|move|go|take|put|log)\\s+(me\\s+)?(over\\s+|back\\s+|in\\s+)?(to|as|into)\\s+(the\\s+|a\\s+)?(officer|citizen|chief secretary|cs|madam)\\b", low)''',
     '''    if re.search(r"[\\u0c80-\\u0cff]", t) and re.search(r"ವಾಪಸ್|ಹಿಂದೆ|ಹೋಗಿ|ಕರ್ಕೊಂಡು|ಕರೆದುಕೊಂಡು|ತೋರಿಸಿ|ತೆರೆಯಿರಿ|ಮುಚ್ಚಿ|switch|open|go|take", t, re.I):
        kv = "app" if re.search(r"\\bapp\\b|mobile|phone|ಆ್ಯಪ್|ಆಪ್|ಮೊಬೈಲ್|ಫೋನ್", t, re.I) else "web" if re.search(r"\\bweb\\b|website|ವೆಬ್|ಕಂಪ್ಯೂಟರ್", t, re.I) else ""
        kp = "citizen" if re.search(r"citizen|ನಾಗರಿಕ|ಸಿಟಿಜನ್", t, re.I) else "officer" if re.search(r"officer|ಅಧಿಕಾರಿ|ಆಫೀಸರ್|tahsildar|ತಹಶೀಲ್ದಾರ್", t, re.I) else \\
            "cs" if re.search(r"chief secretary|ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿ|\\bcs\\b|madam|ಮೇಡಂ", t, re.I) else ""
        if kv:                                          # Kannada navigation: the same functions as English
            return {"intent": "go_to", "target": (kv + " " + kp).strip()}
        if kp and re.search(r"view|profile|desk|screen|ಪ್ರೊಫೈಲ್|ಪರದೆ|ವ್ಯೂ|ಗೆ", t, re.I):
            return {"intent": "switch_profile", "profile": kp}
        if re.search(r"dashboard|ಡ್ಯಾಶ್|main screen|ಮುಖ್ಯ ಪರದೆ", t, re.I):
            return {"intent": "go_to", "target": "dashboard"}
        if re.search(r"inbox|ಇನ್‌ಬಾಕ್ಸ್|ಇನ್ಬಾಕ್ಸ್", t, re.I):
            return {"intent": "go_to", "target": "inbox"}
        if re.search(r"chart|graph|ಚಾರ್ಟ್", t, re.I) and re.search(r"ಮುಚ್ಚಿ|close", t, re.I):
            return {"intent": "go_to", "target": "dashboard"}
    m = re.search(r"\\b(switch|change|move|go|take|put|log)\\s+(me\\s+)?(over\\s+|back\\s+|in\\s+)?(to|as|into)\\s+(the\\s+|a\\s+)?(officer|citizen|chief secretary|cs|madam)\\b", low)'''),
])

patch("mitra/server/live.py", [
    ('''        "If they ask to switch to the web view / website / desktop or to the app / phone / mobile view (optionally of another profile), call go_to with target 'web' or 'app' plus the profile''',
     '''        "'Citizen view', 'officer view', 'Chief Secretary view' (also in Kannada: ನಾಗರಿಕ / ಅಧಿಕಾರಿ / ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿ view ಗೆ ಹೋಗಿ) mean that PROFILE: call switch_profile, NOT go_to web/app. "
        "If they ask to switch to the web view / website / desktop or to the app / phone / mobile view (optionally of another profile), call go_to with target 'web' or 'app' plus the profile'''),
])
print("done")
