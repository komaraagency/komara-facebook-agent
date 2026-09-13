from __future__ import annotations

"""Normalisation de texte pour matching fuzzy + intention.
Le bot doit comprendre l'intention, pas juste les mots-clés exacts.
Tolérant aux fautes d'orthographe, abréviations SMS, et français africain.
"""

import re
import unicodedata

def normalize_text(text: str) -> str:
    """Alias de normalize() pour compatibilité avec l'ancien code."""
    return normalize(text)


# Corrections orthographiques courantes (FR + AFrique + SMS)
COMMON_FIXES = {
    # Salutations
    "bonjor": "bonjour", "bonjur": "bonjour", "bjr": "bonjour", "bjr": "bonjour",
    "bonsoir": "bonsoir", "bsr": "bonsoir", "bsr": "bonsoir",
    "salut": "salut", "slt": "salut", "coucou": "salut", "cc": "salut",
    "salam": "salam", "salamalikoum": "salam", "salmaalikum": "salam",
    "bonjours": "bonjour", "bonsoirs": "bonsoir",

    # Komara / agence
    "komara": "komara", "komra": "komara", "komarra": "komara",
    "agence": "agence", "agenc": "agence", "agance": "agence",

    # Prix / argent
    "prix": "prix", "prx": "prix", "combien": "combien", "comb1": "combien",
    "cout": "coute", "coute": "coute", "couter": "coute", "couté": "coute",
    "cher": "cher", "chere": "cher", "chers": "cher", "chères": "cher",
    "devis": "devis", "dvis": "devis", "devi": "devis",
    "tarif": "tarif", "tarifs": "tarif", "tarife": "tarif",

    # Bot / tech
    "bot": "bot", "chatbot": "chatbot", "chat boot": "chatbot", "chatbots": "chatbot",
    "whatsapp": "whatsapp", "whatsap": "whatsapp", "watsapp": "whatsapp",
    "watsap": "whatsapp", "whatspp": "whatsapp", "whtasp": "whatsapp",
    "telegram": "telegram", "telegrm": "telegram", "tg": "telegram",
    "site": "site", "siteweb": "site web", "site web": "site web",
    "logo": "logo", "logos": "logo",
    "ia": "ia", "inteligence": "intelligence",
    "automatiser": "automatiser", "automatisation": "automatisation",
    "auto": "automatisation", "automatique": "automatisation",

    # Vente / business
    "vendre": "vendre", "vend": "vendre", "vente": "vente", "vents": "vente",
    "commercial": "commercial", "commerciale": "commercial",
    "client": "client", "clients": "client", "customer": "client",
    "commande": "commande", "commandé": "commande", "cmd": "commande",

    # Services
    "service": "service", "servic": "service", "services": "service",
    "formation": "formation", "formtion": "formation", "formaton": "formation",
    "restaurant": "restaurant", "resto": "restaurant",
    "clinique": "clinique", "sante": "sante", "santé": "sante",
    "immobilier": "immobilier", "immo": "immobilier",
    "ecommerce": "ecommerce", "e-commerce": "ecommerce",

    # Abonnement / paiement
    "abonnement": "abonnement", "abonement": "abonnement", "abo": "abonnement",
    "paye": "payer", "payer": "payer", "peye": "payer",
    "orange": "orange", "money": "money", "orange_money": "orange money",

    # Divers
    "merci": "merci", "mrci": "merci", "mrc": "merci",
    "comment": "comment", "coment": "comment", "comme": "comme",
    "facebook": "facebook", "facebok": "facebook", "fb": "facebook",
    "messenger": "messenger", "messengr": "messenger",
    "instagram": "instagram", "insta": "instagram",
    "garantie": "garantie", "garanti": "garantie",
    "securite": "securite", "sécurité": "securite", "securiter": "securite",
    "support": "support", "supor": "support", "supor": "support",
    "pourquoi": "pourquoi", "pourkoi": "pourquoi", "pk": "pourquoi",
    "langue": "langue", "langues": "langue",
    "vocal": "vocal", "voix": "vocal",
    "rdv": "rdv", "rendez": "rdv", "rendez-vous": "rdv",
    "agent": "agent", "agents": "agent",
    "ok": "ok", "okay": "ok", "oke": "ok", "dak": "ok", "dac": "ok",
    "oui": "oui", "we": "oui", "yes": "oui",
    "non": "non", "no": "non",
    "boonjour": "bonjour", "bnjour": "bonjour",

    # Abbréviations SMS africaines
    "cv": "sympa", "sa": "sa", "va": "va", "sava": "sava", "sa va": "sava",
    "wsh": "wesh", "wesh": "wesh",
    "tro": "trop", "troop": "trop", "trp": "trop",
    "frerot": "frere", "soeurette": "soeur",
    "biz": "baiser", "bisous": "baiser",
    "nrv": "nerve", "re1": "rien", "ri1": "rien",
    "koi": "quoi", "koif": "quoi",
    "tkt": "t inquiete", "tkt": "t inquiete",
    "c": "c",  # identite : PHRASE_FIXES gere deja "c koi"/"c quoi" (sinon double "est") "cé": "c est",
    "c est": "c est", "c'est": "c est", "cest": "c est",  # cle vivante: apostrophe deja supprimee avant lookup
    "vi": "viande", "viande": "viande",

    # Erreurs grammaticales communes
    "je veut": "je veux", "je vé": "je veux",
    "tu peut": "tu peux", "il peut": "il peut",
    "nous veux": "nous voulons", "vous veut": "vous voulez",
    "faut": "faut", "fo": "faut",
    "g": "j ai", "j'ai": "j ai", "j ai": "j ai", "jé": "j ai", "jai": "j ai",

    # Création
    "creer": "creer", "cree": "creer", "creez": "creer", "créer": "creer",
    "création": "creation", "creation": "creation", "creaton": "creation",
    "developper": "developper", "develop": "developper",
    "construire": "construire", "construir": "construire", "monte": "monte",

    # Contact
    "contacter": "contacter", "contact": "contacter", "contacté": "contacter",
    "appele": "appeler", "appeler": "appeler", "apel": "appeler",
    "numéro": "numero", "numero": "numero", "numer": "numero",
    "whatsapp_numero": "numero whatsapp",
}

# Mapping intention → mots associés (pour la détection d'intention)
INTENT_MAP = {
    "prix_tarif": ["prix", "cout", "combien", "tarif", "coute", "cher", "paye", "euro", "fg", "mad", "fcfa", "argent", "budget", "commission", "abonnement", "mensuel", "facture", "devis", "dollar"],
    "presentation": ["komara", "agence", "presentation", "qui", "faites", "services", "propose", "quipe", "c est quoi", "salut", "bonjour", "bonsoir", "hello", "hi", "coucou", "quoi", "komara agency"],
    "agent_vs_chatbot": ["agent", "chatbot", "difference", "vs", "comparaison", "robot", "bot"],
    "automatisation": ["automatiser", "automatisation", "automatique", "automatiser business", "taches"],
    "rdv": ["rdv", "rendez", "rendez-vous", "appointment", "agenda", "booking", "creneau", "rendez vous"],
    "support": ["support", "aide", "aide", "probleme", "urgence", "erreur", "bloque", "panne", "assistance"],
    "technique": ["technique", "securise", "securite", "rgpd", "hebergement", "serveur", "api", "cloud", "ollama", "connexion", "internet", "3g", "gdpr", "meta"],
    "langues": ["langue", "langues", "francais", "anglais", "soussou", "malinke", "pular", "multilingue"],
    "whatsapp": ["whatsapp", "whatsap", "watsapp", "messenger", "instagram", "api", "meta"],
    "resultats": ["resultat", "ventes", "ca", "chiffre", "roi", "rentabiliser", "augmenter", "fidele", "gagner", "revenu"],
    "garantie": ["garantie", "satisfait", "remboursement", "essai", "test", "demo"],
    "secteur": ["secteur", "restaurant", "immobilier", "clinique", "formation", "ecommerce", "garage", "voyage", "coach", "photographe", "avocat", "ecole", "coiffure", "ong", "voiture", "boutique", "resto"],
    "objection": ["trop cher", "pas besoin", "pas sur", "peur", "robot", "remplacer", "complique", "pas tech", "arret", "mentir", "marche afrique", "risque", "securite"],
    "demarrer": ["commencer", "demarrer", "on commence", "lancer", "je commence", "je lance", "demo", "aujourd", "signer", "etal", "etapes", "installer", "installation", "setup"],
    "futur": ["futur", "prochaine", "roadmap", "application", "app", "vision", "5 ans", "lever", "r&d", "labo"],
    "marketing": ["pub", "publicite", "facebook ads", "contenu", "tiktok", "promo", "soldes", "cross selling", "upsell", "panier", "avis", "fidelis", "video", "reels"],
    "croissance": ["scaler", "grandir", "100 clients", "b2b", "international", "partenariat", "recruter", "fideliser", "remote", "pays"],
    "creation": ["creer", "creez", "developper", "construire", "souhaite", "voudrais", "aimerais", "besoin", "nouveau", "faire", "avoir", "create", "build", "make", "want", "need"],
    "availability": ["nuit", "weekend", "24", "disponibilite", "ferie", "jour", "night", "hours", "available", "24/7", "24h", "3h"],
    "commande": ["commande", "commander", "order", "panier", "acheter", "livraison", "livrer"],
}


def remove_accents(text: str) -> str:
    """Supprime les accents pour un matching plus tolérant."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# Corrections multi-mots (phrases) à appliquer AVANT le traitement mot par mot
PHRASE_FIXES = {
    "mer ci": "merci",
    "merçi": "merci",
    "me rc i": "merci",
    "bon jour": "bonjour",
    "bon soi r": "bonsoir",
    "site webe": "site web",
    "chat boot": "chatbot",
    "wat sap": "whatsapp",
    "what sap": "whatsapp",
    "c koi": "c est quoi",
    "c quoi": "c est quoi",
    "c koi l agence": "c est quoi l agence",
    "sa va": "ca va",
    "je veu": "je veux",
    "je veut": "je veux",
    "je vé": "je veux",
    "je voudré": "je voudrais",
    "j aimeré": "j aimerais",
    "je souaite": "je souhaite",
    "je souete": "je souhaite",
    "coment sa marche": "comment ca marche",
    "coment ca marche": "comment ca marche",
    "koman sa marche": "comment ca marche",
}


def normalize(message: str) -> str:
    """Normalise un message: minuscules, sans accents, fautes corrigées.

    Tolérant aux fautes courantes (FR + Afrique + SMS):
    - Accents supprimés: é→e, à→a
    - Fautes corrigées: bonjor→bonjour, whatsap→whatsapp
    - Abbréviations: bjr→bonjour, slt→salut, cv→sympa
    - Phases corrigées: "mer ci"→"merci", "c koi"→"c est quoi"
    - Grammaire approximative tolérée
    """
    if not message:
        return ""
    # Minuscules
    text = message.lower().strip()
    # Suppression accents
    text = remove_accents(text)
    # Nettoyage: espaces multiples → un seul
    text = re.sub(r'\s+', ' ', text)
    # 1. Corrections multi-mots d'abord (phrases, avant que l'apostrophe soit touchee)
    # BUG corrige : le simple str.replace matchait les SOUS-CHAINES.
    # "je veu" (cle) se retrouvait DANS "je veux" (valeur deja appliquee)
    # -> "veux" devenait "veuxx", "veut" devenait "veuxt".
    # On applique chaque correction avec des bords de mots stricts.
    # BUG corrige 2 : les cles accentuees ("je vé") etaient du code mort
    # car remove_accents passe AVANT -> on desaccentue aussi les cles.
    fixes = {remove_accents(k): v for k, v in PHRASE_FIXES.items()}
    for bad, good in fixes.items():
        pattern = r'(?<![a-z0-9])' + re.escape(bad) + r'(?![a-z0-9])'
        text = re.sub(pattern, good.replace('\\', '\\\\'), text)
    # 1bis. Apostrophe = separateur de mots, jamais une fusion.
    # BUG corrige : "l'info" devenait "linfo" (mot fusionne, illisible pour le
    # matching) au lieu de "l info" -> "info" reste identifiable.
    text = re.sub(r"[''’]", ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # 2. Correction des fautes courantes (mot par mot)
    words = text.split()
    fixed = []
    for w in words:
        # Nettoyage ponctuation
        w_clean = re.sub(r'[^\w\s-]', '', w)
        if not w_clean:
            continue
        # Correction si connue
        if w_clean in COMMON_FIXES:
            fixed.append(COMMON_FIXES[w_clean])
        else:
            fixed.append(w_clean)
    return ' '.join(fixed)


def detect_intent(message: str) -> str | None:
    """Détecte l'intention d'un message (pas juste les mots-clés).
    Retourne la catégorie d'intention ou None.
    """
    norm = normalize(message)
    if not norm:
        return None

    # Score pour chaque intention
    scores = {}
    for intent, keywords in INTENT_MAP.items():
        score = 0
        for kw in keywords:
            kw_norm = remove_accents(kw.lower())
            if kw_norm in norm:
                score += len(kw_norm.split())  # Les mots longs comptent plus
        if score > 0:
            scores[intent] = score

    if scores:
        best = max(scores, key=scores.get)
        return best
    return None


def fuzzy_match(word1: str, word2: str, threshold: float = 0.75) -> bool:
    """Match approximatif entre deux mots (tolérance fautes).
    Utilise la distance de Levenshtein.

    Tolerance:
    - 1 faute pour mots de 4-5 lettres
    - 2 fautes pour mots de 6+ lettres
    """
    if not word1 or not word2:
        return False
    if word1 == word2:
        return True
    if len(word1) < 3 or len(word2) < 3:
        return word1 == word2

    # Ancre: la premiere lettre doit matcher. Les vraies fautes de frappe
    # changent rarement la premiere lettre, et ca elimine les faux positifs
    # (ex: "ecoute" ne matchera jamais "coute")
    if word1[0] != word2[0]:
        return False

    # Distance de Levenshtein
    m, n = len(word1), len(word2)
    # Optimisation: si la différence de longueur est trop grande, pas de match
    if abs(m - n) > 2:
        return False

    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    dist = dp[m][n]
    max_len = max(m, n)
    similarity = 1 - (dist / max_len)
    return similarity >= threshold


def score_match(message: str, tags: list, questions: list) -> float:
    """Score de matching entre un message et une entrée de la KB.
    Combine matching exact, fuzzy, et intention.
    """
    norm_msg = normalize(message)
    if not norm_msg:
        return 0.0

    norm_tags = [remove_accents(t.lower()) for t in tags]
    norm_questions = [remove_accents(q.lower()) for q in questions]

    msg_words = set(norm_msg.split())
    score = 0.0

    # 1. Matching direct sur tags
    for tag in norm_tags:
        tag_words = tag.split()
        tag_found = False
        for tw in tag_words:
            if tw in msg_words:
                score += 2.0
                tag_found = True
            else:
                # 2. Fuzzy match sur mots du tag
                for mw in msg_words:
                    if fuzzy_match(tw, mw, 0.75):
                        score += 1.0
                        tag_found = True
                        break
        # Bonus si le tag complet est dans le message
        if tag in norm_msg:
            score += 3.0

    return score
