
import re
import unicodedata
from typing import Any, Dict, List, Optional

from database import execute_query


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = unicodedata.normalize("NFD", name)
    name = "".join(ch for ch in name if unicodedata.category(ch) != "Mn")
    name = re.sub(r"\s+", " ", name.upper().strip())
    return name


def calculate_similarity(name1: str, name2: str) -> float:
    name1 = normalize_name(name1)
    name2 = normalize_name(name2)
    if not name1 or not name2:
        return 0.0
    words1 = set(name1.split())
    words2 = set(name2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)


def normalize_country(country: Optional[str]) -> Optional[str]:
    if not country:
        return None
    c = country.strip().upper()
    mapping = {
        "PORTUGAL": "PT",
        "PT": "PT",
        "ANGOLA": "AO",
        "AO": "AO",
        "BRASIL": "BR",
        "BRAZIL": "BR",
        "BR": "BR",
        "MOÇAMBIQUE": "MZ",
        "MOCAMBIQUE": "MZ",
        "MZ": "MZ",
    }
    return mapping.get(c, c[:3])


def perform_matching(search_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    try:
        country = search_data.get("country")

        if search_data.get("full_name"):
            name_matches = execute_query(
                """
                SELECT 
                    ne.id, ne.full_name, ne.nif, ne.passport, ne.resident_card,
                    ne.position, ne.country, ne.additional_info,
                    s.name AS source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true
                  AND LOWER(ne.full_name) LIKE LOWER(%s)
                """,
                (f"%{search_data['full_name']}%",),
            )
            for match in name_matches:
                similarity = calculate_similarity(
                    search_data["full_name"], match["full_name"]
                )
                if similarity <= 0.3:
                    continue

                match_country = match.get("country")
                country_bonus = 0.0
                if country and match_country:
                    norm_match_country = normalize_country(match_country)
                    if norm_match_country == country:
                        country_bonus = 0.2

                matches.append(
                    {
                        "type": "name_match",
                        "similarity": min(1.0, similarity + country_bonus),
                        "source": match["source_name"],
                        "source_type": match["source_type"],
                        "full_name": match["full_name"],
                        "nif": match["nif"],
                        "passport": match["passport"],
                        "resident_card": match["resident_card"],
                        "position": match["position"],
                        "country": match["country"],
                        "additional_info": match["additional_info"],
                    }
                )

        if search_data.get("nif"):
            nif_matches = execute_query(
                """
                SELECT ne.*, s.name AS source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.nif = %s
                """,
                (search_data["nif"],),
            )
            for match in nif_matches:
                matches.append(
                    {
                        "type": "nif_match",
                        "similarity": 1.0,
                        "source": match["source_name"],
                        "source_type": match["source_type"],
                        "full_name": match["full_name"],
                        "nif": match["nif"],
                        "passport": match.get("passport"),
                        "resident_card": match.get("resident_card"),
                        "position": match["position"],
                        "country": match["country"],
                        "additional_info": match.get("additional_info"),
                    }
                )

        if search_data.get("passport"):
            passport_matches = execute_query(
                """
                SELECT ne.*, s.name AS source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.passport = %s
                """,
                (search_data["passport"],),
            )
            for match in passport_matches:
                matches.append(
                    {
                        "type": "passport_match",
                        "similarity": 1.0,
                        "source": match["source_name"],
                        "source_type": match["source_type"],
                        "full_name": match["full_name"],
                        "nif": match.get("nif"),
                        "passport": match["passport"],
                        "resident_card": match.get("resident_card"),
                        "position": match["position"],
                        "country": match["country"],
                        "additional_info": match.get("additional_info"),
                    }
                )

        if search_data.get("resident_card"):
            card_matches = execute_query(
                """
                SELECT ne.*, s.name AS source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.resident_card = %s
                """,
                (search_data["resident_card"],),
            )
            for match in card_matches:
                matches.append(
                    {
                        "type": "resident_card_match",
                        "similarity": 1.0,
                        "source": match["source_name"],
                        "source_type": match["source_type"],
                        "full_name": match["full_name"],
                        "nif": match.get("nif"),
                        "passport": match.get("passport"),
                        "resident_card": match["resident_card"],
                        "position": match["position"],
                        "country": match["country"],
                        "additional_info": match.get("additional_info"),
                    }
                )

    except Exception as e:
        print(f"Erro na busca por matches: {e}")

    return matches


def calculate_risk_score(
    matches: List[Dict[str, Any]], has_nif: bool = False, search_country: Optional[str] = None
) -> Dict[str, Any]:
    base_score = 0
    risk_factors: List[str] = []

    if not matches:
        return {
            "score": 10,
            "level": "LOW",
            "factors": ["Nenhum match encontrado nas bases de dados"],
        }

    for match in matches:
        match_type = match.get("type", "")
        source_type = match.get("source_type", "")
        similarity = match.get("similarity", 0.0)

        if source_type == "PEP":
            base_score += 40
            risk_factors.append(
                f"Match em lista PEP: {match.get('full_name', 'N/A')}"
            )
        elif source_type == "SANCTIONS":
            base_score += 50
            risk_factors.append(
                f"Match em lista de sanções: {match.get('full_name', 'N/A')}"
            )
        elif source_type == "FRAUD":
            base_score += 60
            risk_factors.append(
                f"Match em lista de fraude: {match.get('full_name', 'N/A')}"
            )
        elif source_type == "CLAIMS":
            base_score += 30
            risk_factors.append(
                f"Histórico de sinistros: {match.get('full_name', 'N/A')}"
            )

        if match_type in ["nif_match", "passport_match", "resident_card_match"]:
            base_score += 20
        elif match_type == "name_match" and similarity > 0.8:
            base_score += 15
        elif match_type == "name_match" and similarity > 0.5:
            base_score += 10

        if search_country:
            match_country = normalize_country(match.get("country"))
            if match_country and match_country != search_country:
                base_score -= 5
                risk_factors.append(
                    "País/nacionalidade do match diferente do informado na pesquisa"
                )
            elif match_country and match_country == search_country:
                base_score += 5
                risk_factors.append(
                    "País/nacionalidade do match coincide com o informado na pesquisa"
                )

    if has_nif:
        base_score += 5
        risk_factors.append("Possui NIF para verificação")

    final_score = min(100, max(0, base_score))

    if final_score <= 25:
        risk_level = "LOW"
    elif final_score <= 50:
        risk_level = "MEDIUM"
    elif final_score <= 75:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    return {"score": final_score, "level": risk_level, "factors": risk_factors}
