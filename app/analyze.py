# -*- coding: utf-8 -*-
"""TD text -> structured JSON -> Markdown fiche de révision."""
from __future__ import annotations

import json
import re

from llm import chat

SYSTEM = """Tu es professeur de mathématiques en classe préparatoire française (SPEIT, SJTU ParisTech).
Tu produis des fiches de révision fidèles au corrigé officiel fourni.
Tu écris un français mathématique rigoureux et concis.
Chaque terme technique français est suivi d'une glose chinoise entre parenthèses.
Tu ne réinventes pas les solutions : tu reformules et expliques le corrigé.
Tu réponds uniquement par un objet JSON valide, sans texte avant ou après."""

USER_TEMPLATE = """Cours : {course}
TD : {td}

Corrigé officiel (texte extrait du PDF) :
----------------
{source}
----------------

Produis la fiche détaillée du TD. Réponds en JSON avec exactement ces clés :
- title : titre très court (≤ 6 mots)
- course : "{course}"
- td : "{td}"
- exercises : liste des exercices du TD. Ne coupe pas un exercice dont les sous-questions sont les étapes d'une même démonstration ; garde-le entier avec "Question 1/2" dans solution. Coupe seulement les exercices à sous-questions indépendantes (ex. quatre équations) en "Exercice 4.1", "Exercice 4.2", etc.
  Chaque entrée a :
  - no : "Exercice 1" ou "Exercice 4.1" ...
  - theme_zh : type d'exercice en chinois
  - statement_fr : énoncé complet ; toute notation mathématique en $...$
  - statement_zh : traduction chinoise complète ; toute notation mathématique en $...$ (pas de symboles nus ∈, ⊂, ⊕, =)
  - statement_notes : 2–4 puces chinoises expliquant chaque hypothèse/condition ; toute notation en $...$
  - knowledge : 0–3 objets. Ne force pas 3. N'inclus que de vraies notions : définition, théorème, formule.
      Ne répète pas un knowledge déjà donné dans une autre entrée du même TD : les notions génériques (degré, identification, analyse-synthèse) ne doivent apparaître qu'une seule fois.
      Chaque objet a :
      - title : terme chinois court
      - fr : terme français
      - body : 2–3 phrases chinoises : définition + usage de base/conditions ; toute notation mathématique en $...$
      - formulas : 0–2 formules LaTeX
      N'explique pas "comment on l'utilise dans cet exercice" ; si c'est une astuce de solution, mets-la dans idea.
      Pas de phrases tautologiques ("le produit est un produit") ni de body d'une seule phrase creuse.
      Exemple correct :
      {{"title": "递归法", "fr": "raisonnement par récurrence", "body": ["先验证初始项成立的证明方法。", "适用于对所有整数 n 成立的命题；必须同时验证初始化和归纳步。"], "formulas": ["P(1)\\\\text{{ et }}(P(k)\\\\Rightarrow P(k+1))\\\\Rightarrow \\\\forall k,P(k)"]}}
  - subquestions : si l'exercice a plusieurs questions 1./2. qui font partie d'une même démonstration, garde l'exercice entier et mets chaque question dans un objet :
      - label_zh : "第 1 问"
      - label_fr : "Question 1. Montrer que ..." (reprends l'énoncé de la question)
      - idea : 3–6 étapes numérotées, propres à cette question ; toute notation en $...$
      - solution : étapes propres à cette question, SANS label ("Étape 1" interdit) ; mêmes blocs text/math que ci-dessous.
      Ne mélange jamais les questions dans une même liste idea/solution.
  - idea : pour un exercice sans sous-questions : 3–6 étapes numérotées. Chaque étape dit quoi faire + pourquoi ; toute notation mathématique doit être en $...$ (ex. $G\subset H$, $F\cap G=\{0_E\}$).
  - solution : liste d'étapes SANS label ("Étape 1" est interdit). Chaque étape a :
      - blocks : 1–4 blocs. Deux types :
          * text : fr = phrase de liaison (connecteurs + conditions + théorème inline, avec $...$) ; zh = traduction complète (mêmes notations inline, avec $...$). Si la formule clé est dans le bloc math suivant, arrête la phrase sur "on a / on obtient / d'où" et NE LA RÉPÈTE PAS dans fr/zh.
          * math : la formule/conclusion clé à afficher centrée, une seule fois.
      Chaque étape qui contient une formule/conclusion clé doit avoir au moins un bloc math ; ne mets pas toutes les formules inline. Les étapes purement textuelles peuvent n'avoir que du text.
      Regroupe "et", "donc", "or", "comme" dans la phrase : ne fais pas un bloc pour chaque connecteur. Si une condition est secondaire, laisse-la inline dans fr/zh.
      Chaque bloc text doit avoir fr et zh NON VIDES. Exemple de forme :
      {"blocks": [{"type": "text", "fr": "Comme $G\\subset H$, on a l'inclusion suivante.", "zh": "因为 $G\\subset H$，所以有下面的包含关系。"}, {"type": "math", "tex": "F\\cap G\\subset F\\cap H"}]}
      Mauvais : text "Soit $h\\in H$ ... $h=f+g$." puis math "h=f+g" (la formule est répétée).
      Bon : text "Soit $h\\in H$ ... il existe $f,g$ tels que" puis math "h=f+g" ; le text s'arrête avant la formule.
      Mauvais : text "Finalement on conclut $H=G$." puis math "H=G". Bon : text "Finalement on conclut que" puis math "H=G".

Contraintes :
- Reste fidèle au corrigé ; ne change pas les résultats.
- Sois détaillé mais contenu : 2–4 pages par exercice (sous-questions comprises), 1–4 blocs par étape, 8 étapes maximum par sous-question. Pas de paraphrase ni de phrases de remplissage.
- Les formules doivent être en LaTeX : $...$ en ligne, $$...$$ pour une formule centrée.
- Pas de tableaux Markdown. Pas de texte hors du JSON."""


def clean_source(text: str) -> str:
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    text = text.replace("ﬃ", "ffi").replace("ﬄ", "ffl")
    text = re.sub(r"SPEIT 巴院.*?Page\s*\d+\s*/\s*\d+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(raw[start:end + 1])


def _pairs(value) -> list[dict]:
    out = []
    for item in value or []:
        if isinstance(item, dict):
            out.append({"fr": str(item.get("fr", "")).strip(),
                        "zh": str(item.get("zh", "")).strip()})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append({"fr": str(item[0]).strip(), "zh": str(item[1]).strip()})
        elif isinstance(item, str):
            out.append({"fr": item.strip(), "zh": ""})
    return out


def _solution(value) -> list[dict]:
    out = []
    for item in value or []:
        if isinstance(item, dict):
            out.append({"fr": str(item.get("fr", "")).strip(),
                        "zh": str(item.get("zh", "")).strip()})
        else:
            out.append({"fr": str(item).strip(), "zh": ""})
    return out


def normalize(data: dict, course: str, td: str) -> dict:
    data.setdefault("title", "TD")
    data.setdefault("course", course)
    data.setdefault("td", td)
    data["exercises"] = data.get("exercises") or []
    for index, exercise in enumerate(data["exercises"], 1):
        exercise.setdefault("no", f"Exercice {index}")
        exercise.setdefault("theme_zh", exercise.get("theme", ""))
        exercise.setdefault("statement_fr", exercise.get("statement", ""))
        exercise.setdefault("statement_zh", "")
        notes = exercise.get("statement_notes") or []
        if isinstance(notes, str):
            notes = [notes]
        exercise["statement_notes"] = [str(x).strip() for x in notes if str(x).strip()]
        knowledge = []
        for item in exercise.get("knowledge") or []:
            if isinstance(item, dict):
                body = item.get("body") or []
                if isinstance(body, str):
                    body = [body]
                formulas = item.get("formulas") or []
                if isinstance(formulas, str):
                    formulas = [formulas]
                knowledge.append({
                    "title": item.get("title") or item.get("zh") or item.get("fr", ""),
                    "fr": item.get("fr", ""),
                    "body": [str(x).strip() for x in body if str(x).strip()],
                    "formulas": [str(x).strip() for x in formulas if str(x).strip()],
                })
            elif isinstance(item, str):
                knowledge.append({"title": item, "fr": "", "body": [], "formulas": []})
        exercise["knowledge"] = knowledge

        idea = []
        for item in exercise.get("idea") or []:
            if isinstance(item, dict):
                text = re.sub(r"^\s*\d+[.)、]\s*", "", str(item.get("text", "")).strip())
                idea.append({"text": text,
                             "formula": str(item.get("formula", "")).strip()})
            else:
                idea.append({"text": re.sub(r"^\s*\d+[.)、]\s*", "", str(item).strip()),
                             "formula": ""})
        exercise["idea"] = idea

        solution = []
        for item in exercise.get("solution") or []:
            if isinstance(item, dict):
                blocks = []
                for block in item.get("blocks") or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "math":
                        blocks.append({"type": "math", "tex": str(block.get("tex", "")).strip()})
                    else:
                        blocks.append({"type": "text",
                                       "fr": str(block.get("fr", "")).strip(),
                                       "zh": str(block.get("zh", "")).strip()})
                solution.append({"label": str(item.get("label", "")).strip(),
                                 "fr": str(item.get("fr", "")).strip(),
                                 "zh": str(item.get("zh", "")).strip(),
                                 "formula": str(item.get("formula", "")).strip(),
                                 "blocks": blocks})
            else:
                solution.append({"label": "", "fr": str(item).strip(), "zh": "", "formula": "", "blocks": []})
        exercise["solution"] = solution

        subquestions = []
        for sq in exercise.get("subquestions") or []:
            if not isinstance(sq, dict):
                continue
            sq_idea = []
            for item in sq.get("idea") or []:
                if isinstance(item, dict):
                    text = re.sub(r"^\s*\d+[.)、]\s*", "", str(item.get("text", "")).strip())
                    sq_idea.append({"text": text,
                                    "formula": str(item.get("formula", "")).strip()})
                else:
                    sq_idea.append({"text": re.sub(r"^\s*\d+[.)、]\s*", "", str(item).strip()),
                                    "formula": ""})
            sq_solution = []
            for item in sq.get("solution") or []:
                if isinstance(item, dict):
                    blocks = []
                    for block in item.get("blocks") or []:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "math":
                            blocks.append({"type": "math", "tex": str(block.get("tex", "")).strip()})
                        else:
                            blocks.append({"type": "text",
                                           "fr": str(block.get("fr", "")).strip(),
                                           "zh": str(block.get("zh", "")).strip()})
                    sq_solution.append({"label": str(item.get("label", "")).strip(),
                                        "fr": str(item.get("fr", "")).strip(),
                                        "zh": str(item.get("zh", "")).strip(),
                                        "formula": str(item.get("formula", "")).strip(),
                                        "blocks": blocks})
                else:
                    sq_solution.append({"label": "", "fr": str(item).strip(), "zh": "", "formula": "", "blocks": []})
            subquestions.append({
                "label_zh": str(sq.get("label_zh", "")).strip(),
                "label_fr": str(sq.get("label_fr", "")).strip(),
                "idea": sq_idea,
                "solution": sq_solution,
            })
        exercise["subquestions"] = subquestions

    # Do not repeat the same generic knowledge across sub-exercises.
    seen_titles = set()
    for exercise in data["exercises"]:
        filtered = []
        for item in exercise.get("knowledge", []):
            key = (item.get("title") or item.get("fr") or "").strip()
            if key and key in seen_titles:
                continue
            if key:
                seen_titles.add(key)
            filtered.append(item)
        exercise["knowledge"] = filtered
    return data


def analyze(course: str, td: str, source: str, model: str | None = None,
            max_tokens: int | None = None) -> tuple[dict, str, dict]:
    source = clean_source(source)
    template = USER_TEMPLATE.replace("{{", "{").replace("}}", "}")
    prompt = (template.replace("{course}", course)
                      .replace("{td}", td)
                      .replace("{source}", source))
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    raw, usage = chat(messages, model=model, max_tokens=max_tokens)
    try:
        data = normalize(parse_json(raw), course, td)
    except Exception:
        repair = messages + [
            {"role": "assistant", "content": raw[:12000]},
            {"role": "user", "content": "Ta réponse n'est pas un JSON valide. Réponds uniquement avec le JSON demandé, sans commentaire."},
        ]
        raw2, usage2 = chat(repair, model=model, max_tokens=max_tokens)
        data = normalize(parse_json(raw2), course, td)
        raw, usage = raw2, usage2
    return data, raw, usage


def _short_title(data: dict) -> str:
    title = data.get("title") or "TD"
    title = title.split(":", 1)[0].strip()
    return title[:60] or "TD"


def to_markdown(data: dict, mode: str = "detail") -> str:
    course = data.get("course", "")
    td = data.get("td", "")
    lines: list[str] = [f"# {course} · {td} · {_short_title(data)}", ""]

    if mode == "quick":
        lines.append("### 速览")
        lines.append("")
        for exercise in data["exercises"]:
            idea = exercise["idea"][0] if exercise["idea"] else ""
            lines.append(
                f"- **{exercise['no']}** {exercise['theme']} — 关键：{idea}；结果：{exercise['answer']}"
            )
        lines.append("")
        for exercise in data["exercises"]:
            lines.append(f"## {exercise['no']} · {exercise['theme']}")
            lines.append("")
            if exercise["statement"]:
                lines.append(f"**题干** {exercise['statement']}")
                lines.append("")
            if exercise["knowledge"]:
                lines.append("**知识点**")
                lines.append("")
                for item in exercise["knowledge"]:
                    suffix = f"（{item['zh']}）" if item["zh"] else ""
                    lines.append(f"- **{item['fr']}**{suffix}")
                lines.append("")
            if exercise["idea"]:
                lines.append("**思路**")
                lines.append("")
                for item in exercise["idea"]:
                    lines.append(f"- {item}")
                lines.append("")
            if exercise["solution"]:
                first = exercise["solution"][0]
                zh = f"（{first['zh']}）" if first["zh"] else ""
                lines.append(f"**起步** {first['fr']}{zh}")
                lines.append("")
            if exercise["answer"]:
                lines.append(f"**结果** {exercise['answer']}")
                lines.append("")
            if exercise["pitfall"]:
                lines.append(f"**易错 / 存疑** {exercise['pitfall']}")
                lines.append("")
        return "\n".join(lines).strip() + "\n"

    lines.append("### 速览")
    lines.append("")
    for exercise in data["exercises"]:
        idea = exercise["idea"][0] if exercise["idea"] else ""
        lines.append(
            f"- **{exercise['no']}** {exercise['theme']} — 关键：{idea}；结果：{exercise['answer']}"
        )
    lines.append("")
    for exercise in data["exercises"]:
        lines.append(f"## {exercise['no']} · {exercise['theme']}")
        lines.append("")
        if exercise["statement"]:
            lines.append(f"**题干** {exercise['statement']}")
            lines.append("")
        if exercise["knowledge"]:
            lines.append("**知识点**")
            lines.append("")
            for item in exercise["knowledge"]:
                suffix = f"（{item['zh']}）" if item["zh"] else ""
                lines.append(f"- **{item['fr']}**{suffix}")
            lines.append("")
        if exercise["idea"]:
            lines.append("**思路**")
            lines.append("")
            for item in exercise["idea"]:
                lines.append(f"- {item}")
            lines.append("")
        if exercise["solution"]:
            lines.append("**解答**")
            lines.append("")
            for index, step in enumerate(exercise["solution"], 1):
                zh = f"（{step['zh']}）" if step["zh"] else ""
                lines.append(f"{index}. {step['fr']}{zh}")
            lines.append("")
        if exercise["pitfall"]:
            lines.append(f"**易错 / 存疑** {exercise['pitfall']}")
            lines.append("")
    if data["glossary"]:
        lines.append("### 术语表")
        lines.append("")
        for item in data["glossary"]:
            suffix = f"（{item['zh']}）" if item["zh"] else ""
            lines.append(f"- **{item['fr']}**{suffix}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
